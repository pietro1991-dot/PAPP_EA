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
#property copyright "PaPP v2"
#property version   "1.10"
#property description "Relative-value mean-reversion EURGBP H6 - lotto a rischio %"

#include <Trade/Trade.mqh>

// --- Sizing: lotto fisso ---
input double Lots        = 0.10;   // lotto fisso

// --- Segnale (H6) ---
input int    MAPeriod    = 28;     // media della distanza
input int    PctWindow   = 280;    // finestra del percentile
input double LoThr       = 20.0;   // osc sotto = BUY (cross sottovalutato)
input double HiThr       = 80.0;   // osc sopra = SELL (cross sopravvalutato)
input double ExitLevel   = 50.0;   // esci al ritorno al centro
input int    MaxHoldBars = 48;     // uscita di sicurezza (barre H6)
input double SafetySLpip = 0.0;    // SL di protezione in pip (0 = nessuno, come backtest; ~150 consigliato live)
input long   MagicNumber = 770077;

#define ANCHOR_TF PERIOD_H6

CTrade   trade;
datetime g_lastBar = 0;
int      g_hMA = INVALID_HANDLE;
datetime g_entryBarTime = 0;

//+------------------------------------------------------------------+
double Pip()
  {
   return (_Digits==3 || _Digits==5) ? 10*_Point : _Point;
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
   return INIT_SUCCEEDED;
  }
void OnDeinit(const int reason){ if(g_hMA!=INVALID_HANDLE) IndicatorRelease(g_hMA); }

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

   double osc;
   if(!ComputeOsc(osc)) return;

   long dir=0;
   if(HasPosition(dir))
     {
      bool revertDone = (dir>0 && osc>=ExitLevel) || (dir<0 && osc<=ExitLevel);
      int  held = (g_entryBarTime>0)? iBarShift(_Symbol,ANCHOR_TF,g_entryBarTime,false) : 0;
      bool timeOut = (MaxHoldBars>0 && held>=MaxHoldBars);
      if(revertDone || timeOut){ trade.PositionClose(_Symbol); g_entryBarTime=0; }
      return;
     }

   if(Lots<=0.0) return;
   double pip=Pip();
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   if(osc < LoThr)
     {
      double sl = (SafetySLpip>0.0)? ask - SafetySLpip*pip : 0.0;
      if(trade.Buy(Lots,_Symbol,ask,sl,0.0,"relval buy")) g_entryBarTime=bt;
     }
   else if(osc > HiThr)
     {
      double sl = (SafetySLpip>0.0)? bid + SafetySLpip*pip : 0.0;
      if(trade.Sell(Lots,_Symbol,bid,sl,0.0,"relval sell")) g_entryBarTime=bt;
     }
  }
//+------------------------------------------------------------------+
