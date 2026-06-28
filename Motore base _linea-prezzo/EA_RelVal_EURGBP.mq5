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

// --- Sizing a rischio percentuale (come gli altri EA PaPP) ---
input double RiskPct        = 2.0;     // rischio % equity per trade (0 con LotFixed)
input double LotFixed       = 0.0;     // lotto fisso (0 = usa RiskPct)
input double MaxLot         = 5.0;     // tetto di sicurezza al lotto (0 = max broker)
input double FallbackRiskPips = 150.0; // distanza di rischio in pip per il sizing quando non c'e' SL hard

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
// Lotto dal rischio %: risk = Equity*RiskPct/100; lotto = risk/(ticks*tickVal).
// riskDist = distanza in PREZZO a cui corrisponde la perdita "1R".
double CalcLot(double riskDistPrice)
  {
   if(LotFixed > 0.0)
      return (MaxLot>0.0) ? MathMin(LotFixed,MaxLot) : LotFixed;
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk   = equity * RiskPct / 100.0;
   if(risk<=0.0 || riskDistPrice<=0.0) return 0.0;
   double tickVal  = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickVal<=0.0 || tickSize<=0.0) return 0.0;
   double ticks  = riskDistPrice / tickSize;
   double lotRaw = risk / (ticks * tickVal);
   double step   = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxBrk = SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double lot    = MathFloor(lotRaw/step)*step;
   double cap    = (MaxLot>0.0) ? MathMin(maxBrk,MaxLot) : maxBrk;
   return MathMax(minLot, MathMin(lot, cap));
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

   double pip=Pip();
   double riskDist = ((SafetySLpip>0.0)? SafetySLpip : FallbackRiskPips) * pip;
   double lot = CalcLot(riskDist);
   if(lot<=0.0) return;
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   if(osc < LoThr)
     {
      double sl = (SafetySLpip>0.0)? ask - SafetySLpip*pip : 0.0;
      if(trade.Buy(lot,_Symbol,ask,sl,0.0,"relval buy")) g_entryBarTime=bt;
     }
   else if(osc > HiThr)
     {
      double sl = (SafetySLpip>0.0)? bid + SafetySLpip*pip : 0.0;
      if(trade.Sell(lot,_Symbol,bid,sl,0.0,"relval sell")) g_entryBarTime=bt;
     }
  }
//+------------------------------------------------------------------+
