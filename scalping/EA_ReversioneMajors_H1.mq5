//+------------------------------------------------------------------+
//|                                    EA_ReversioneMajors_H1.mq5     |
//|                                                        PaPP v2    |
//|  Reversione (mean-reversion) sulle MAJORS, timeframe H1, usando   |
//|  la distanza del prezzo dalla LINEA MEDIAN (PaPP_Median, D1-anchor).|
//|                                                                    |
//|  NB: lo SCALPING M5 e' stato BOCCIATO (cross/breakout/overext.     |
//|  veloce: nessun edge, i breakout PERDONO). L'edge vero e' la       |
//|  REVERSIONE a orizzonte ~1-2 giorni. Validato 2026-07-01 su        |
//|  EUR/USD H1 2010-2026 (split 2020): TEST PF 1.25-1.31 anche a      |
//|  costo 25pt, ~80 trade/anno, quasi ogni anno positivo. Stessa      |
//|  meccanica di EA_RelVal, riferimento = Median invece della MA.     |
//|                                                                    |
//|  Segnale (H1): osc = percentile (PctWindow) della distanza         |
//|  close-Median. osc<Lo -> BUY, osc>Hi -> SELL. Esci a osc=ExitLevel |
//|  (ritorno alla media) o dopo MaxHold barre. Una posizione/volta.   |
//|                                                                    |
//|  RICHIEDE PaPP_Median.ex5 in MQL5/Indicators e papp_push.mqh in    |
//|  MQL5/Include. Metti l'EA su un grafico EUR/USD (o GBP/USD, USD/CHF)|
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Reversione majors H1 su distanza dalla Median - lotto a rischio %"

#include <Trade/Trade.mqh>
#include <papp_push.mqh>          // libreria condivisa (mettila in MQL5/Include)

// --- Riferimento: la linea MEDIAN (D1-anchored) via PaPP_Median ---
input string InpIndicator = "PaPP_Median.ex5"; // stesso indicatore del Motore Base
#define BUF_MEDIAN 0

// --- Sizing: percentuale di capitale, scala col BALANCE attuale (come EA_RelVal) ---
input double PctCapitale = 25.0;    // % di capitale (25 = profilo sano; scala col conto = compounding)
input double MaxLot      = 0.0;     // tetto di sicurezza al lotto (0 = nessuno)

// --- Vol-targeting: size piu' piccola quando la volatilita' e' alta ---
input bool   VolTarget   = true;    // scala la size con la volatilita' (controlla il DD)
input int    VolFast     = 40;      // barre H1 per la vol corrente
input int    VolSlow     = 2000;    // barre H1 per la vol di riferimento (~3 mesi)
input double VolFloor    = 0.30;    // fattore minimo
input double VolCap      = 2.50;    // fattore massimo

// --- Segnale (H1) — parametri VALIDATI nel backtest ---
input int    PctWindow   = 300;    // finestra del percentile (H1 ~12 giorni). Robusto anche a 500/800.
input double LoThr       = 5.0;    // osc sotto = BUY  (config migliore 5/95 W=300 hold 48; alt: 10/90)
input double HiThr       = 95.0;   // osc sopra = SELL
input double ExitLevel   = 50.0;   // esci al ritorno al centro (reversione completata)
input int    MaxHoldBars = 48;     // uscita di tempo (barre H1 = 2 giorni). Validato.
input double SafetySLpip = 400.0;  // SL di SICUREZZA (NON nel backtest: rete anti-gap/flash. Ampio = raro).
input double TPlongPip   = 0.0;    // 0 = niente TP fisso (esci al ritorno osc=50, come nel backtest)
input double TPshortPip  = 0.0;
input long   MagicNumber = 660066;

// --- Telemetria PHAI (manda i segnali al chatbot) ---
input bool   InpUseServer  = false;                  // OWNER: false. Cliente: il .set lo mette true
input string InpServerUrl  = "https://app.phai.io";  // autorizzalo in Strumenti>Opzioni>EA>WebRequest
input string InpLicenseKey = "";                     // License key PHAI
input string InpLogFile    = "papp_ea_log.jsonl";    // log locale (vuoto = off)

#define ANCHOR_TF PERIOD_H1

CTrade   trade;
datetime g_lastBar = 0;
int      g_hMed = INVALID_HANDLE;
datetime g_entryBarTime = 0;
bool     g_licensed = false;

//+------------------------------------------------------------------+
double Pip(){ return (_Digits==3 || _Digits==5) ? 10*_Point : _Point; }

//+------------------------------------------------------------------+
// Fattore vol-targeting: rif/corrente, limitato a [VolFloor,VolCap].
double VolFactor()
  {
   if(!VolTarget) return 1.0;
   int need = VolSlow+2;
   double cl[]; ArraySetAsSeries(cl,true);
   if(CopyClose(_Symbol,ANCHOR_TF,0,need,cl) < need) return 1.0;
   double r[]; ArrayResize(r,VolSlow);
   for(int k=0;k<VolSlow;k++) r[k] = (cl[k+1]>0)? MathLog(cl[k]/cl[k+1]) : 0.0;
   double mf=0,ms=0;
   for(int k=0;k<VolFast;k++) mf+=r[k]; mf/=VolFast;
   for(int k=0;k<VolSlow;k++) ms+=r[k]; ms/=VolSlow;
   double sf=0,ss=0;
   for(int k=0;k<VolFast;k++){ double d=r[k]-mf; sf+=d*d; }
   for(int k=0;k<VolSlow;k++){ double d=r[k]-ms; ss+=d*d; }
   double fast=MathSqrt(sf/MathMax(1,VolFast-1));
   double slow=MathSqrt(ss/MathMax(1,VolSlow-1));
   if(fast<=0.0) return 1.0;
   return MathMax(VolFloor, MathMin(VolCap, slow/fast));
  }

//+------------------------------------------------------------------+
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
   if(StringFind(_Symbol,"EURUSD")<0 && StringFind(_Symbol,"GBPUSD")<0 && StringFind(_Symbol,"USDCHF")<0)
      Print("ATTENZIONE: EA validato su EUR/USD (e majors), simbolo attuale = ",_Symbol);
   // riferimento = linea Median (D1-anchored), stessi input dell'export/Motore Base
   g_hMed = iCustom(_Symbol,ANCHOR_TF,InpIndicator, 9, false, true, true, C'20,20,25', true);
   if(g_hMed==INVALID_HANDLE){ Print("iCustom PaPP_Median fallito. Copia PaPP_Median.ex5 in MQL5/Indicators."); return INIT_FAILED; }
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   PappInit(InpUseServer, InpServerUrl, InpLicenseKey);
   string _lf = (StringLen(InpLogFile)>0 && InpLogFile!="papp_ea_log.jsonl") ? InpLogFile : ("papp_ea_"+_Symbol+".jsonl");
   PappLogOpen(_lf);
   EventSetTimer(15);
   PrintFormat("PAPP Reversione %s H1 avviato | server=%s | key=%s | logfile=%s",
               _Symbol,(InpUseServer?"on":"off"),(StringLen(InpLicenseKey)>0?"si":"no"),_lf);
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){ if(g_hMed!=INVALID_HANDLE) IndicatorRelease(g_hMed); EventKillTimer(); PappLogClose(); }

//+------------------------------------------------------------------+
// Stato LIVE (barra 0, prezzo corrente) — solo telemetria.
bool ComputeRelval(double &osc, double &dist, double &vol)
  {
   if(BarsCalculated(g_hMed) < PctWindow+2) return false;
   double md[]; double cl[];
   ArraySetAsSeries(md,true); ArraySetAsSeries(cl,true);
   if(CopyBuffer(g_hMed,BUF_MEDIAN,0,PctWindow+2,md) < PctWindow+1) return false;
   if(CopyClose(_Symbol,ANCHOR_TF,0,PctWindow+2,cl) < PctWindow+1) return false;
   dist = (md[0]>0)? (cl[0]-md[0])/md[0]*100.0 : 0.0;
   int below=0, tot=0; double sum=0, sum2=0;
   for(int k=1;k<=PctWindow;k++){ if(md[k]<=0.0) continue;
      double d=(cl[k]-md[k])/md[k]*100.0;
      if(d<=dist) below++; tot++; sum+=d; sum2+=d*d; }
   if(tot<=0) return false;
   osc = 100.0*(double)below/(double)tot;
   double mean=sum/tot, var=(sum2/tot)-mean*mean; if(var<0) var=0;
   vol = MathSqrt(var);
   return true;
  }

//+------------------------------------------------------------------+
int g_timerN  = 0;
int g_barsOut = 0;
void OnTimer()
  {
   g_timerN++;
   bool beat = (g_timerN <= 3 || g_timerN % 20 == 0);
   PappAccount(_Symbol);
   double osc, dist, vol; int bars = BarsCalculated(g_hMed);
   if(!ComputeRelval(osc, dist, vol))
     {
      if(beat) PrintFormat("PAPP %s: oscillatore non pronto (barre=%d, servono %d).",
                           _Symbol, bars, PctWindow+2);
      return;
     }
   long pdir=0; bool hasPos=HasPosition(pdir);
   double toBuy  = (osc>LoThr)? osc-LoThr : 0.0;
   double toSell = (osc<HiThr)? HiThr-osc : 0.0;
   string info = hasPos ? (pdir>0?"posizione LONG aperta":"posizione SHORT aperta")
               : (osc<=LoThr?"in zona BUY":(osc>=HiThr?"in zona SELL":"in attesa"));
   PappRelval(_Symbol, osc, dist, vol, toBuy, toSell, g_barsOut, info);
   if(beat) PrintFormat("PAPP %s: osc=%.1f dist=%.3f%% vol=%.3f toBUY=%.0f toSELL=%.0f | %s",
                        _Symbol, osc, dist, vol, toBuy, toSell, info);
  }

//+------------------------------------------------------------------+
// osc (0..100) sull'ultima barra H1 CHIUSA. distanza[k]=(close-Median)/Median*100.
bool ComputeOsc(double &osc)
  {
   if(BarsCalculated(g_hMed) < PctWindow+2) return false;
   double md[]; double cl[];
   ArraySetAsSeries(md,true); ArraySetAsSeries(cl,true);
   if(CopyBuffer(g_hMed,BUF_MEDIAN,0,PctWindow+2,md) < PctWindow+1) return false;
   if(CopyClose(_Symbol,ANCHOR_TF,0,PctWindow+2,cl) < PctWindow+1) return false;
   double dist[]; ArrayResize(dist,PctWindow);
   for(int k=0;k<PctWindow;k++)
     {
      int idx=k+1;   // barre CHIUSE 1..PctWindow (niente barra 0 in formazione)
      dist[k] = (md[idx]>0) ? (cl[idx]-md[idx])/md[idx]*100.0 : 0.0;
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

   g_licensed = PappValidate(_Symbol, IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));

   double osc;
   if(!ComputeOsc(osc)) return;
   g_barsOut = (osc<=LoThr || osc>=HiThr) ? g_barsOut+1 : 0;

   double pip=Pip();
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   long dir=0;
   if(HasPosition(dir))
     {
      double entryPx = PositionGetDouble(POSITION_PRICE_OPEN);
      double lc   = iClose(_Symbol,ANCHOR_TF,1);
      double move = (lc-entryPx)/pip*dir;

      bool revertDone = (dir>0 && osc>=ExitLevel) || (dir<0 && osc<=ExitLevel);
      int  held = (g_entryBarTime>0)? iBarShift(_Symbol,ANCHOR_TF,g_entryBarTime,false) : 0;
      bool timeOut = (MaxHoldBars>0 && held>=MaxHoldBars);
      if(revertDone || timeOut){
         if(trade.PositionClose(_Symbol))
            PappSignal("close",_Symbol,(int)(dir>0?1:2),0,0,0,0,(dir>0?bid:ask),move,timeOut?"uscita max-hold":"uscita osc=50");
         g_entryBarTime=0;
        }
      return;
     }

   // nessuna posizione: nuova entrata di reversione
   if(!g_licensed) return;
   double lot=CalcLot();
   if(lot<=0.0) return;

   if(osc < LoThr)
     {
      double sl = (SafetySLpip>0.0)? ask - SafetySLpip*pip : 0.0;
      double tp = (TPlongPip >0.0)? ask + TPlongPip *pip : 0.0;
      if(trade.Buy(lot,_Symbol,ask,sl,tp,"reversione buy")){ g_entryBarTime=bt;
         PappSignal("open",_Symbol,1,ask,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f<%.0f",osc,LoThr)); }
     }
   else if(osc > HiThr)
     {
      double sl = (SafetySLpip>0.0)? bid + SafetySLpip*pip : 0.0;
      double tp = (TPshortPip>0.0)? bid - TPshortPip*pip : 0.0;
      if(trade.Sell(lot,_Symbol,bid,sl,tp,"reversione sell")){ g_entryBarTime=bt;
         PappSignal("open",_Symbol,2,bid,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f>%.0f",osc,HiThr)); }
     }
  }
//+------------------------------------------------------------------+
