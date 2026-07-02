//+------------------------------------------------------------------+
//|                                    EA_ReversioneMajors_H1.mq5     |
//|                                                        PaPP v2    |
//|  Reversione (mean-reversion) sulle MAJORS, timeframe H1, usando   |
//|  la distanza del prezzo dalla LINEA MEDIAN (D1-anchored).          |
//|                                                                    |
//|  Legge la Median dal tuo indicatore PaPP_Median con lo STESSO      |
//|  metodo di EA_EURUSD: handle su D1 (g_indD1) + ReadBufD1. Il       |
//|  Strategy Tester PRECARICA la storia D1 per quell'handle (per      |
//|  questo EA_EURUSD gira nel tester). Serve PaPP_Median.ex5 in       |
//|  MQL5/Indicators (come per il Motore Base).                        |
//|                                                                    |
//|  NB: lo SCALPING M5 e' stato BOCCIATO (cross/breakout: nessun edge,|
//|  i breakout PERDONO). L'edge vero e' la REVERSIONE a ~1-2 giorni.  |
//|  Validato 2026-07-01 su EUR/USD H1 2010-2026 (split 2020):         |
//|  TEST PF 1.25-1.31 anche a costo 25pt, ~80 trade/anno.             |
//|                                                                    |
//|  Segnale (H1): osc = percentile (PctWindow) della distanza         |
//|  close-Median. osc<Lo -> BUY, osc>Hi -> SELL. Esci a osc=ExitLevel |
//|  o dopo MaxHold barre. Una posizione/volta.                        |
//|                                                                    |
//|  Metti l'EA su un grafico EUR/USD (o GBP/USD, USD/CHF).            |
//|  Richiede papp_push.mqh in MQL5/Include.                           |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.10"
#property description "Reversione majors H1 su distanza dalla Median (self-contained) - lotto a rischio %"

#include <Trade/Trade.mqh>
#include <papp_push.mqh>          // libreria condivisa (mettila in MQL5/Include)

// --- Riferimento: la linea MEDIAN via PaPP_Median (come EA_EURUSD) ---
input string InpIndicator = "PaPP_Median.ex5";
#define BUF_MEDIAN 0

// --- Sizing: percentuale di capitale, scala col BALANCE attuale ---
// QUESTO e' il motore del profitto €: 25 = prudente (lotto piccolo, +61%/16y nel test).
// Alzalo per PIU' profitto ma PIU' drawdown, in proporzione (50=doppio, 100=leva piena).
input double PctCapitale = 25.0;    // % di capitale. La leva profitto/DD: alza per piu' €.
input double MaxLot      = 0.0;     // tetto di sicurezza al lotto (0 = nessuno)

// --- Vol-targeting: OFF di default (non era nel backtest validato; su H1 va ri-tarato) ---
input bool   VolTarget   = false;   // false = size piena costante (come il backtest). true solo con VolSlow rivisto per H1.
input int    VolFast     = 40;
input int    VolSlow     = 6000;    // se attivi VolTarget su H1: ~1 anno (2000 era per H6, troppo corto)
input double VolFloor    = 0.30;
input double VolCap      = 2.50;

// --- Segnale (H1) — parametri VALIDATI nel backtest ---
input int    PctWindow   = 300;    // finestra del percentile (H1 ~12 giorni). Robusto anche a 500/800.
input double LoThr       = 5.0;    // osc sotto = BUY  (config migliore 5/95 W=300 hold 48)
input double HiThr       = 95.0;   // osc sopra = SELL
input double ExitLevel   = 50.0;   // esci al ritorno al centro
input int    MaxHoldBars = 48;     // uscita di tempo (barre H1 = 2 giorni). Validato.
input double SafetySLpip = 0.0;    // 0 = come il backtest (nessuno stop, esci a osc=50/MaxHold). Per il LIVE metti 300-400 come rete anti-gap.
input double TPlongPip   = 0.0;    // 0 = niente TP fisso (esci al ritorno osc=50)
input double TPshortPip  = 0.0;
input long   MagicNumber = 660066;

// --- Telemetria PHAI ---
input bool   InpUseServer  = false;
input string InpServerUrl  = "https://app.phai.io";
input string InpLicenseKey = "";
input string InpLogFile    = "papp_ea_log.jsonl";

#define ANCHOR_TF PERIOD_H1

CTrade   trade;
datetime g_lastBar = 0;
int      g_ind   = INVALID_HANDLE;   // PaPP_Median sul TF H1 (fallback)
int      g_indD1 = INVALID_HANDLE;   // PaPP_Median sul D1 (sorgente principale, come EA_EURUSD)
datetime g_entryBarTime = 0;
bool     g_licensed = false;
bool     g_tester   = false;   // true nel Strategy Tester: niente telemetria/timer (solo trading)

//+------------------------------------------------------------------+
double Pip(){ return (_Digits==3 || _Digits==5) ? 10*_Point : _Point; }
bool   IsPriceOk(double v){ return (v>0.0 && v<1.0e12); }

//+------------------------------------------------------------------+
// Legge la MEDIAN alla barra D1 'd1Shift' (come ReadBufD1 di EA_EURUSD):
// prima dall'handle D1, altrimenti dal chart H1 proiettato sulla stessa D1.
bool ReadMedianD1(int d1Shift, double &val)
  {
   datetime d1Time = iTime(_Symbol,PERIOD_D1,d1Shift);
   if(d1Time==0) return false;
   double tmp[1];
   if(g_indD1!=INVALID_HANDLE)
     {
      if(CopyBuffer(g_indD1,BUF_MEDIAN,d1Shift,1,tmp)==1 && IsPriceOk(tmp[0])){ val=tmp[0]; return true; }
     }
   int chartShift = iBarShift(_Symbol,ANCHOR_TF,d1Time,false);
   if(chartShift<0) return false;
   if(CopyBuffer(g_ind,BUF_MEDIAN,chartShift,1,tmp)!=1) return false;
   val=tmp[0];
   return IsPriceOk(val);
  }

//+------------------------------------------------------------------+
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
   g_ind = iCustom(_Symbol,ANCHOR_TF,InpIndicator, 9, false, true, true, C'20,20,25', true);
   if(g_ind==INVALID_HANDLE){ Print("iCustom PaPP_Median (H1) fallito. Copia PaPP_Median.ex5 in MQL5/Indicators."); return INIT_FAILED; }
   g_indD1 = iCustom(_Symbol,PERIOD_D1,InpIndicator, 9, false, true, true, C'20,20,25', true);
   if(g_indD1==INVALID_HANDLE) Print("WARNING: g_indD1 fallito - usero' il fallback H1");
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(20);
   g_tester = (bool)MQLInfoInteger(MQL_TESTER);
   if(!g_tester)          // nel tester: niente telemetria/log/timer (inutili + rallentano)
     {
      PappInit(InpUseServer, InpServerUrl, InpLicenseKey);
      string _lf = (StringLen(InpLogFile)>0 && InpLogFile!="papp_ea_log.jsonl") ? InpLogFile : ("papp_ea_"+_Symbol+".jsonl");
      PappLogOpen(_lf);
      EventSetTimer(15);
      PrintFormat("PAPP Reversione %s H1 avviato | server=%s | key=%s",
                  _Symbol,(InpUseServer?"on":"off"),(StringLen(InpLicenseKey)>0?"si":"no"));
     }
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason)
  {
   if(g_ind!=INVALID_HANDLE)   IndicatorRelease(g_ind);
   if(g_indD1!=INVALID_HANDLE) IndicatorRelease(g_indD1);
   EventKillTimer(); PappLogClose();
  }

//+------------------------------------------------------------------+
// Median (D1-anchored) su ogni barra H1: mediana delle 7 MA D1 alla D1 della barra.
// osc = percentile della distanza (close-Median)/Median sulle ultime PctWindow barre H1
// CHIUSE. Ritorna anche dist0 (distanza corrente %) e vol (dev.std distanze) per telemetria.
bool ComputeCore(double &osc, double &dist0, double &vol)
  {
   int need = PctWindow+2;
   double cl[]; datetime tm[];
   ArraySetAsSeries(cl,true); ArraySetAsSeries(tm,true);
   if(CopyClose(_Symbol,ANCHOR_TF,0,need,cl) < need) return false;
   if(CopyTime (_Symbol,ANCHOR_TF,0,need,tm) < need) return false;

   double dist[]; ArrayResize(dist,PctWindow);
   for(int k=0;k<PctWindow;k++)
     {
      int idx = k+1;                                               // barre CHIUSE 1..PctWindow
      // Median del D1 CHIUSO PRECEDENTE (shift+1): l'export usa il gradino "no look-ahead"
      // (durante il giorno D vale la MA del giorno D-1). Con shift 0 il D1 in formazione
      // insegue il prezzo intraday e schiaccia il segnale -> uscite premature.
      int d1s = iBarShift(_Symbol,PERIOD_D1,tm[idx],false) + 1;
      if(d1s<1) return false;
      double med;
      if(!ReadMedianD1(d1s,med)) return false;                     // Median D1 (warm-up gestito qui)
      dist[k] = (cl[idx]-med)/med*100.0;
     }
   double cur = dist[0]; int below=0; double sum=0,sum2=0;
   for(int k=0;k<PctWindow;k++){ if(dist[k]<=cur) below++; sum+=dist[k]; sum2+=dist[k]*dist[k]; }
   osc  = 100.0*(double)below/PctWindow;
   dist0 = cur;
   double mean=sum/PctWindow, var=(sum2/PctWindow)-mean*mean; if(var<0) var=0;
   vol = MathSqrt(var);
   return true;
  }
bool ComputeOsc(double &osc){ double d,v; return ComputeCore(osc,d,v); }

//+------------------------------------------------------------------+
int g_timerN  = 0;
int g_barsOut = 0;
void OnTimer()
  {
   if(g_tester) return;                 // nessuna telemetria nel backtest
   g_timerN++;
   bool beat = (g_timerN <= 3 || g_timerN % 20 == 0);
   PappAccount(_Symbol);
   double osc, dist, vol;
   if(!ComputeCore(osc, dist, vol))
     {
      if(beat) PrintFormat("PAPP %s: oscillatore non pronto (MA D1 in warm-up).",_Symbol);
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

   g_licensed = g_tester ? true : PappValidate(_Symbol, IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)));

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
         if(trade.PositionClose(_Symbol) && !g_tester)
            PappSignal("close",_Symbol,(int)(dir>0?1:2),0,0,0,0,(dir>0?bid:ask),move,timeOut?"uscita max-hold":"uscita osc=50");
         g_entryBarTime=0;
        }
      return;
     }

   if(!g_licensed) return;
   double lot=CalcLot();
   if(lot<=0.0) return;

   if(osc < LoThr)
     {
      double sl = (SafetySLpip>0.0)? ask - SafetySLpip*pip : 0.0;
      double tp = (TPlongPip >0.0)? ask + TPlongPip *pip : 0.0;
      if(trade.Buy(lot,_Symbol,ask,sl,tp,"reversione buy")){ g_entryBarTime=bt;
         if(!g_tester) PappSignal("open",_Symbol,1,ask,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f<%.0f",osc,LoThr)); }
     }
   else if(osc > HiThr)
     {
      double sl = (SafetySLpip>0.0)? bid + SafetySLpip*pip : 0.0;
      double tp = (TPshortPip>0.0)? bid - TPshortPip*pip : 0.0;
      if(trade.Sell(lot,_Symbol,bid,sl,tp,"reversione sell")){ g_entryBarTime=bt;
         if(!g_tester) PappSignal("open",_Symbol,2,bid,sl,tp,lot,0,0,StringFormat("reversione osc=%.0f>%.0f",osc,HiThr)); }
     }
  }
//+------------------------------------------------------------------+
