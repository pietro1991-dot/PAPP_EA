//+------------------------------------------------------------------+
//|                                              EA_RelVal_EURGBP.mq5 |
//|                                                        PaPP v2     |
//|  Relative-value mean-reversion su EURGBP, timeframe H6.           |
//|  Edge validato 2026-06-28: il cross cancella la gamba USD -> resta |
//|  il valore relativo, che mean-reverte. H6: ~35 trade/anno,        |
//|  PF 1.19/1.40 train/test, R/DD test 3.1, 13/17 anni positivi.     |
//|                                                                    |
//|  Segnale (H6): osc = percentile (PctWindow) della distanza        |
//|  close-MA. osc<Lo -> BUY, osc>Hi -> SELL. Esci a osc=ExitLevel(50) |
//|  o dopo MaxHold barre. Una posizione/volta. Lotto a RISCHIO %.     |
//|  Mettere su grafico EURGBP (lavora internamente su H6).           |
//+------------------------------------------------------------------+
#property copyright "PHAI v2"
#property version   "1.10"
#property description "Relative-value mean-reversion EURGBP H6 - lotto a rischio %"

#include <Trade/Trade.mqh>
#include <phai_push.mqh>          // libreria condivisa (mettila in MQL5/Include)

// --- Sizing: percentuale di capitale, scala col BALANCE attuale ---
// PctCapitale = 100 -> 1 lotto ogni 10.000 di balance corrente. Cresce col conto:
//   10k -> 1 lotto, 20k -> 2 lotti, 40k -> 4. 50 = meta' size, 200 = doppia.
// NB: scalando col conto COMPONE -> amplifica il drawdown%. Default 25 = punto di
//   equilibrio validato (con SAR=80: ~+215% in 16 anni, DD ~33%). 100 = leva piena
//   (+1613% ma DD ~85%, non tradabile). Alza solo se accetti piu' drawdown.
input double PctCapitale = 25.0;    // % di capitale. Allineato al backtest: Net +110%, DD 21%, PF 1.25.
                                    // 25 = profilo sano. NON superare 25 (a 85 DD 61%, a 100 blow-up).
input double QuotaConto   = 52.0;   // PORTAFOGLIO Difensivo 2-EA: quota conto di questo EA (%). Preimpostato a 52 (risk-parity).
input double MaxLot      = 0.0;     // tetto di sicurezza al lotto (0 = nessuno)

// --- Vol-targeting: size piu' piccola quando la volatilita' e' alta (rimpicciolisce gli anni-disastro tipo 2016) ---
input bool   VolTarget   = true;    // true = scala la size con la volatilita' (validato: R/DD 4.5->5.4, 2016 -458->-245)
input int    VolFast     = 40;      // barre per la vol corrente
input int    VolSlow     = 2000;    // barre per la vol di RIFERIMENTO (lungo: ~1.4 anni). 480 era troppo corto: si adattava al regime e non proteggeva il 2016. 2000 -> R/DD 4.5->5.5, 2016 -458->-273
input double VolFloor    = 0.30;    // fattore minimo (vol molto alta)
input double VolCap      = 2.50;    // fattore massimo (vol molto bassa)

// --- Segnale (H6) ---
input int    MAPeriod    = 28;     // media della distanza
input int    PctWindow   = 280;    // finestra del percentile
input double LoThr       = 10.0;   // osc sotto = BUY (validato: 10/90 meglio di 15 e 20; oltre=5/95 troppo pochi trade)
input double HiThr       = 90.0;   // osc sopra = SELL
input double ExitLevel   = 50.0;   // esci al ritorno al centro
input int    MaxHoldBars = 4800;   // uscita di sicurezza (barre H6). 4800 = di fatto nessun limite di
                                   // tempo: tieni fino alla reversione (osc=50) o allo stop. Allineato al backtest.
input double TPlongPip   = 25.0;   // TP fisso sulle BUY in pip. Allineato al backtest (con SL=200, hold fino a reversione).
input double TPshortPip  = 25.0;   // TP fisso sulle SELL in pip. Allineato al backtest.
input double SafetySLpip = 200.0;  // SL di protezione in pip. Allineato al backtest: con MaxHold=4800
                                   // (nessun limite di tempo) lo stop a 200 pip e' l'unico taglio-perdite.
input double SARpip      = 0.0;    // Stop-and-Reverse (0 = OFF). Test onesto su dati reali: PEGGIORA (whipsaw). Lasciare 0.
input long   MagicNumber = 770077;

// --- Telemetria PHAI (manda i segnali al chatbot) ---
input bool   InpUseServer  = false;                  // OWNER: false = nessuna licenza, dati via ponte locale. Cliente: il .set lo mette true
input string InpServerUrl  = "https://app.phai.io";  // URL server (autorizzalo in Strumenti>Opzioni>EA>WebRequest)
input string InpLicenseKey = "";                     // License key PHAI (dal tuo account)
input string InpLogFile    = "papp_ea_log.jsonl";    // log locale (ponte chatbot sulla stessa macchina; vuoto=off)

#define ANCHOR_TF PERIOD_H6

CTrade   trade;
datetime g_lastBar = 0;
int      g_hMA = INVALID_HANDLE;
datetime g_entryBarTime = 0;
bool     g_reversed = false;        // true se in questa sequenza abbiamo gia' invertito (SAR)
bool     g_licensed = false;        // licenza valida + simbolo posseduto (validato a ogni barra)

//+------------------------------------------------------------------+
double Pip()
  {
   return (_Digits==3 || _Digits==5) ? 10*_Point : _Point;
  }

//+------------------------------------------------------------------+
// Fattore vol-targeting: rif/corrente, limitato a [VolFloor,VolCap].
// Vol alta -> fattore < 1 (size piu' piccola); vol bassa -> fattore > 1.
double VolFactor()
  {
   if(!VolTarget) return 1.0;
   int need = VolSlow+2;
   double cl[]; ArraySetAsSeries(cl,true);
   if(CopyClose(_Symbol,ANCHOR_TF,0,need,cl) < need) return 1.0;
   double r[]; ArrayResize(r,VolSlow);
   for(int k=0;k<VolSlow;k++) r[k] = (cl[k+1]>0)? MathLog(cl[k]/cl[k+1]) : 0.0;  // log-rendimenti
   double mf=0,ms=0;
   for(int k=0;k<VolFast;k++) mf+=r[k]; mf/=VolFast;
   for(int k=0;k<VolSlow;k++) ms+=r[k]; ms/=VolSlow;
   double sf=0,ss=0;
   for(int k=0;k<VolFast;k++){ double d=r[k]-mf; sf+=d*d; }
   for(int k=0;k<VolSlow;k++){ double d=r[k]-ms; ss+=d*d; }
   double fast=MathSqrt(sf/MathMax(1,VolFast-1));
   double slow=MathSqrt(ss/MathMax(1,VolSlow-1));
   if(fast<=0.0) return 1.0;
   double f = slow/fast;
   return MathMax(VolFloor, MathMin(VolCap, f));
  }

//+------------------------------------------------------------------+
// Lotto = % del BALANCE attuale x fattore vol-targeting. PctCapitale=100 ->
// 1 lotto ogni 10.000 di balance; la vol alta riduce la size (e viceversa).
double CalcLot()
  {
   double cap = AccountInfoDouble(ACCOUNT_BALANCE) * (QuotaConto/100.0);
   double raw = (cap/10000.0) * (PctCapitale/100.0) * VolFactor();
   double step   = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxBrk = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double lotCap = (MaxLot>0.0) ? MathMin(maxBrk,MaxLot) : maxBrk;
   if(step<=0.0) step=0.01;
   double lot = MathFloor(raw/step)*step;
   return MathMax(minLot, MathMin(lot, lotCap));
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   if(StringFind(_Symbol,"EURGBP")<0)
      Print("ATTENZIONE: EA pensato per EURGBP, simbolo attuale = ",_Symbol);
   g_hMA = iMA(_Symbol,ANCHOR_TF,MAPeriod,0,MODE_SMA,PRICE_CLOSE);
   if(g_hMA==INVALID_HANDLE){ Print("iMA fallito"); return INIT_FAILED; }
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   PappInit(InpUseServer, InpServerUrl, InpLicenseKey);
   string _lf = (StringLen(InpLogFile)>0 && InpLogFile!="papp_ea_log.jsonl") ? InpLogFile : ("papp_ea_"+_Symbol+".jsonl");
   PappLogOpen(_lf);          // ponte locale: un file PER EA (niente collisioni di scrittura tra EA)
   EventSetTimer(15);         // export quasi-live (conto + oscillatore) ogni 15s
   PrintFormat("PAPP %s avviato | TF=%s | server=%s | key=%s | logfile=%s",
               _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
               (InpUseServer?"on":"off"), (StringLen(InpLicenseKey)>0?"si":"no"), _lf);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){ if(g_hMA!=INVALID_HANDLE) IndicatorRelease(g_hMA); EventKillTimer(); PappLogClose(); }

//+------------------------------------------------------------------+
// Stato LIVE reversione: usa la barra 0 (in formazione, prezzo corrente). Ritorna
// osc (percentile), dist (distanza corrente dalla media %) e vol (dev.std delle
// distanze sulla finestra = volatilita' del cross). Solo informativo (il trading
// resta su barre chiuse, in ComputeOsc).
bool ComputeRelval(double &osc, double &dist, double &vol)
  {
   if(BarsCalculated(g_hMA) < PctWindow+MAPeriod+2) return false;
   double ma[]; double cl[];
   ArraySetAsSeries(ma,true); ArraySetAsSeries(cl,true);
   if(CopyBuffer(g_hMA,0,0,PctWindow+2,ma) < PctWindow+1) return false;
   if(CopyClose(_Symbol,ANCHOR_TF,0,PctWindow+2,cl) < PctWindow+1) return false;
   dist = (ma[0]>0)? (cl[0]-ma[0])/ma[0]*100.0 : 0.0;
   int below=0, tot=0; double sum=0, sum2=0;
   for(int k=1;k<=PctWindow;k++){ if(ma[k]<=0.0) continue;
      double d=(cl[k]-ma[k])/ma[k]*100.0;
      if(d<=dist) below++; tot++; sum+=d; sum2+=d*d; }
   if(tot<=0) return false;
   osc = 100.0*(double)below/(double)tot;
   double mean=sum/tot, var=(sum2/tot)-mean*mean; if(var<0) var=0;
   vol = MathSqrt(var);
   return true;
  }

//+------------------------------------------------------------------+
// Timer (~15s): export quasi-live di conto + stato (oscillatore col prezzo corrente).
int g_timerN  = 0;   // contatore per loggare ogni tanto (non ad ogni tick)
int g_barsOut = 0;   // barre consecutive in banda estrema (aggiornato in OnTick)
void OnTimer()
  {
   g_timerN++;
   bool beat = (g_timerN <= 3 || g_timerN % 20 == 0);   // log: primi 3 + poi ogni ~5 min
   PappAccount(_Symbol);                 // conto: SEMPRE (non dipende dalle barre)
   double osc, dist, vol; int bars = BarsCalculated(g_hMA);
   if(!ComputeRelval(osc, dist, vol))    // stato + metriche: solo se ci sono abbastanza barre
     {
      if(beat) PrintFormat("PAPP %s: oscillatore non pronto (barre=%d, servono %d). Inviato solo conto (equity=%.2f).",
                           _Symbol, bars, PctWindow+MAPeriod+2, AccountInfoDouble(ACCOUNT_EQUITY));
      return;
     }
   long pdir=0; bool hasPos=HasPosition(pdir);
   double toBuy  = (osc>LoThr)? osc-LoThr : 0.0;   // punti osc per SCENDERE al BUY
   double toSell = (osc<HiThr)? HiThr-osc : 0.0;   // punti osc per SALIRE al SELL
   string info = hasPos ? (pdir>0?"posizione LONG aperta":"posizione SHORT aperta")
               : (osc<=LoThr?"in zona BUY":(osc>=HiThr?"in zona SELL":"in attesa"));
   PappRelval(_Symbol, osc, dist, vol, toBuy, toSell, g_barsOut, info);
   if(beat) PrintFormat("PAPP %s: inviato conto+stato | osc=%.1f dist=%.3f%% vol=%.3f toBUY=%.0f toSELL=%.0f fuori=%d | %s",
                        _Symbol, osc, dist, vol, toBuy, toSell, g_barsOut, info);
  }

//+------------------------------------------------------------------+
// osc (0..100) sull'ultima barra H6 CHIUSA. distanza[k]=(close-MA)/MA*100;
// osc = % di distanze<=corrente sulla finestra [1..PctWindow].
bool ComputeOsc(double &osc)
  {
   if(BarsCalculated(g_hMA) < PctWindow+MAPeriod+2) return false;
   double ma[]; double cl[];
   ArraySetAsSeries(ma,true); ArraySetAsSeries(cl,true);
   if(CopyBuffer(g_hMA,0,0,PctWindow+2,ma) < PctWindow+1) return false;
   if(CopyClose(_Symbol,ANCHOR_TF,0,PctWindow+2,cl) < PctWindow+1) return false;
   double dist[]; ArrayResize(dist,PctWindow);
   for(int k=0;k<PctWindow;k++)
     {
      int idx=k+1;
      dist[k] = (ma[idx]>0) ? (cl[idx]-ma[idx])/ma[idx]*100.0 : 0.0;
     }
   double cur=dist[0]; int below=0;
   for(int k=0;k<PctWindow;k++) if(dist[k]<=cur) below++;
   osc = 100.0*(double)below/PctWindow;
   return true;
  }

//+------------------------------------------------------------------+
bool HasPosition(long &dir)
  {
   for(int i=PositionsTotal()-1;i>=0;i--)
     {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      dir = (PositionGetInteger(POSITION_TYPE)==POSITION_TYPE_BUY)? +1 : -1;
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime bt = iTime(_Symbol,ANCHOR_TF,0);
   if(bt==g_lastBar) return;
   g_lastBar = bt;

   // validazione licenza (a ogni nuova barra): se non autorizzato, niente nuove entrate
   g_licensed = PappValidate(_Symbol, IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));

   double osc;
   if(!ComputeOsc(osc)) return;
   g_barsOut = (osc<=LoThr || osc>=HiThr) ? g_barsOut+1 : 0;   // barre consecutive in banda estrema

   double pip=Pip();
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   long dir=0;
   if(HasPosition(dir))   // HasPosition seleziona la posizione: posso leggerne il prezzo d'entrata
     {
      double entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
      double lc   = iClose(_Symbol,ANCHOR_TF,1);          // ultima barra chiusa
      double move = (lc-entryPx)/pip*dir;                 // pip a favore (negativo = in perdita)

      // STOP-AND-REVERSE: la reversione sta trendando contro -> chiudi e INVERTI sul trend
      if(SARpip>0.0 && !g_reversed && move <= -SARpip)
        {
         double lot=CalcLot();
         if(trade.PositionClose(_Symbol) && lot>0.0)
           {
            if(dir>0) trade.Sell(lot,_Symbol,bid,0.0,0.0,"relval SAR sell");
            else      trade.Buy (lot,_Symbol,ask,0.0,0.0,"relval SAR buy");
            g_reversed=true; g_entryBarTime=bt;
           }
         return;
        }

      // uscita: in reversione esci quando l'osc torna al centro; dopo un SAR (gamba-trend)
      // esci quando l'osc RITORNA dall'estremo verso il centro (logica invertita).
      bool revertDone;
      if(!g_reversed) revertDone = (dir>0 && osc>=ExitLevel) || (dir<0 && osc<=ExitLevel);
      else            revertDone = (dir>0 && osc<=ExitLevel) || (dir<0 && osc>=ExitLevel);
      int  held = (g_entryBarTime>0)? iBarShift(_Symbol,ANCHOR_TF,g_entryBarTime,false) : 0;
      bool timeOut = (MaxHoldBars>0 && held>=MaxHoldBars);
      if(revertDone || timeOut){
         if(trade.PositionClose(_Symbol))
            PappSignal("close",_Symbol,(int)(dir>0?1:2),0,0,0,0,(dir>0?bid:ask),move,timeOut?"uscita max-hold":"uscita osc=50");
         g_entryBarTime=0; g_reversed=false;
        }
      return;
     }

   // nessuna posizione: nuova entrata di reversione
   if(!g_licensed) return;            // licenza non valida o simbolo non posseduto -> niente nuove entrate
   g_reversed=false;
   double lot=CalcLot();
   if(lot<=0.0) return;

   if(osc < LoThr)
     {
      double sl = (SafetySLpip>0.0)? ask - SafetySLpip*pip : 0.0;
      double tp = (TPlongPip >0.0)? ask + TPlongPip *pip : 0.0;
      if(trade.Buy(lot,_Symbol,ask,sl,tp,"relval buy")){ g_entryBarTime=bt;
         PappSignal("open",_Symbol,1,ask,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f<%.0f",osc,LoThr)); }
     }
   else if(osc > HiThr)
     {
      double sl = (SafetySLpip>0.0)? bid + SafetySLpip*pip : 0.0;
      double tp = (TPshortPip>0.0)? bid - TPshortPip*pip : 0.0;
      if(trade.Sell(lot,_Symbol,bid,sl,tp,"relval sell")){ g_entryBarTime=bt;
         PappSignal("open",_Symbol,2,bid,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f>%.0f",osc,HiThr)); }
     }
  }
//+------------------------------------------------------------------+
