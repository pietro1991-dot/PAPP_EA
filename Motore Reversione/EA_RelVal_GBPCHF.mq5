//+------------------------------------------------------------------+
//|                                              EA_RelVal_GBPCHF.mq5 |
//|                                                        PaPP v2     |
//|  Relative-value mean-reversion su GBPCHF, timeframe D1.           |
//|  Edge validato 2026-06-30 sul prezzo GBPCHF REALE: la reversione  |
//|  del valore relativo esiste a ORIZZONTE MENSILE (~28gg), non      |
//|  settimanale come EURGBP. Lo esprimo NATIVAMENTE su D1.            |
//|  Config: MA28 / WIN200 (~10 mesi). Validazione D1 su GBPCHF reale: |
//|  PF 2.60/1.72 train/test, win ~70%, ~8 trade/anno.                |
//|                                                                    |
//|  NB: nel tester il D1 (se secondario) fornisce ~260 barre; per cio'|
//|  WIN200 -> servono 230 barre, ci stanno. NON usare WIN lunghe      |
//|  (es. 252/1008): superano le 260 e l'EA non trada MAI (BarsCalc    |
//|  resta bloccato a 260). Verificato dai log del tester.            |
//|                                                                    |
//|  *** RISCHIO-CODA CHF ***: gamba CHF -> gap SNB (es. 15-01-2015)   |
//|  non copribile (lo stop salta nel gap). Difesa = SIZE RIDOTTA.     |
//|  Default PctCapitale 12 (vs 25 EURGBP). Se usi anche EURCHF,       |
//|  tratta EURCHF+GBPCHF come UN solo secchio di size.               |
//|                                                                    |
//|  Segnale (D1): osc = percentile (PctWindow) della distanza        |
//|  close-MA. osc<Lo -> BUY, osc>Hi -> SELL. Esci a osc=ExitLevel(50) |
//|  o dopo MaxHold barre. Una posizione/volta. Lotto a RISCHIO %.     |
//|  Mettere su grafico GBPCHF (lavora internamente su D1).           |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.10"
#property description "Relative-value mean-reversion GBPCHF D1 (orizzonte mensile) - lotto a rischio %"

#include <Trade/Trade.mqh>
#include <papp_push.mqh>          // libreria condivisa (mettila in MQL5/Include)

// --- Sizing: percentuale di capitale, scala col BALANCE attuale ---
// PctCapitale = 100 -> 1 lotto ogni 10.000 di balance corrente. Cresce col conto.
// NB: scalando col conto COMPONE -> amplifica il drawdown%.
// *** Default 12 (non 25 come EURGBP): GBPCHF ha rischio-coda CHF non copribile;
//     la size piccola e' l'unica vera difesa contro un gap SNB. ***
input double PctCapitale = 25.0;    // % di capitale. 25 = backtest validato: +258% in 16 anni, DD ~54%.
                                    // 54% e' ALTO: per dormire meglio (e rischio-coda CHF) scendi a 12-15.
                                    // NON superare 25: a 100% blow-up (DD 96%). Lo stop NON aiuta (peggiora il DD).
input double MaxLot      = 0.0;     // tetto di sicurezza al lotto (0 = nessuno)

// --- Vol-targeting: size piu' piccola quando la volatilita' e' alta (barre D1) ---
input bool   VolTarget   = true;    // true = scala la size con la volatilita'
input int    VolFast     = 10;      // barre D1 per la vol corrente (~2 settimane)
input int    VolSlow     = 200;     // barre D1 vol di RIFERIMENTO (~10 mesi). Tenuto entro ~260
                                    // perche' nel tester il D1 secondario fornisce ~260 barre.
input double VolFloor    = 0.30;    // fattore minimo (vol molto alta)
input double VolCap      = 2.50;    // fattore massimo (vol molto bassa)

// --- Segnale (D1) - ORIZZONTE MENSILE (config validata su D1) ---
input int    MAPeriod    = 28;     // media della distanza (28 giorni)
input int    PctWindow   = 200;    // finestra del percentile (~10 mesi). 200 (non 252) perche'
                                   // nel tester il D1 secondario da' ~260 barre: 200+28+2=230 ci sta.
                                   // Edge verificato uguale: PF 2.60/1.72 train/test (vs 2.79/1.46 a 252).
input double LoThr       = 10.0;   // osc sotto = BUY
input double HiThr       = 90.0;   // osc sopra = SELL
input double ExitLevel   = 50.0;   // esci al ritorno al centro
input int    MaxHoldBars = 60;     // uscita di sicurezza (60 giorni)
input double TPlongPip   = 0.0;    // TP fisso sulle BUY in pip (0 = esci a osc=50)
input double TPshortPip  = 0.0;    // TP fisso sulle SELL in pip (0 = esci a osc=50)
input double SafetySLpip = 0.0;    // SL di protezione in pip (0 = nessuno; testato: non aiuta)
input double SARpip      = 0.0;    // Stop-and-Reverse (0 = OFF). Lasciare 0.
input long   MagicNumber = 770078; // diverso da EURGBP (770077): possono coesistere

// --- Telemetria PHAI (manda i segnali al chatbot) ---
input bool   InpUseServer  = true;                   // invia i segnali al server PHAI (chatbot)
input string InpServerUrl  = "https://app.phai.io";  // URL server (autorizzalo in Strumenti>Opzioni>EA>WebRequest)
input string InpLicenseKey = "";                     // License key PHAI (dal tuo account)

#define ANCHOR_TF PERIOD_D1

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
   double cap = AccountInfoDouble(ACCOUNT_BALANCE);
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
   if(StringFind(_Symbol,"GBPCHF")<0)
      Print("ATTENZIONE: EA pensato per GBPCHF, simbolo attuale = ",_Symbol);
   g_hMA = iMA(_Symbol,ANCHOR_TF,MAPeriod,0,MODE_SMA,PRICE_CLOSE);
   if(g_hMA==INVALID_HANDLE){ Print("iMA fallito"); return INIT_FAILED; }
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   PappInit(InpUseServer, InpServerUrl, InpLicenseKey);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){ if(g_hMA!=INVALID_HANDLE) IndicatorRelease(g_hMA); }

//+------------------------------------------------------------------+
// osc (0..100) sull'ultima barra D1 CHIUSA. distanza[k]=(close-MA)/MA*100;
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
   static bool firstReady=false;
   if(!firstReady){ firstReady=true;
      Print("RelVal pronto @",TimeToString(bt)," osc=",DoubleToString(osc,1)," BarsCalc=",BarsCalculated(g_hMA)); }

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
