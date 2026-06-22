//+------------------------------------------------------------------+
//|                                                 EA_Crossover.mq5 |
//|                                                        PaPP v2   |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "EA Crossover - Level 1/2 su crossover indicatori PaPP"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";
input int     InpLine1Period   = 365;
input int     InpLine2Period   = 121;
input double  InpRiskPct       = 1.0;
input int     InpTP_Points     = 50;
input int     InpMaxLevel2     = 3;
input int     InpMagic         = 365122;
input bool    InpLog           = true;

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

int      g_ind;
int      g_bufLine1;
int      g_bufLine2;
datetime g_bar0;
bool     g_ready;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

ENUM_POSITION_TYPE g_currentDirection;
int                g_level2Count;

//+------------------------------------------------------------------+
int MAPeriodToBuf(int period)
{
   switch(period)
   {
      case 0:   return BUF_MEDIAN;
      case 365: return BUF_MA365;
      case 182: return BUF_MA182;
      case 121: return BUF_MA121;
      case 30:  return BUF_MA30;
      case 14:  return BUF_MA14;
      case 7:   return BUF_MA7;
      case 3:   return BUF_MA3;
   }
   return BUF_MA365;
}

string MAPeriodStr(int period)
{
   if(period == 0) return "Median";
   return "MA" + IntegerToString(period);
}

//+------------------------------------------------------------------+
bool IsPriceOk(double v)
{
   return (v > 0.0 && v < 1.0e12);
}

//+------------------------------------------------------------------+
bool ReadBuf(int buf, int shift, double &val)
{
   double tmp[1];
   if(CopyBuffer(g_ind, buf, shift, 1, tmp) != 1) return false;
   val = tmp[0];
   return IsPriceOk(val);
}

//+------------------------------------------------------------------+
void CloseAll()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;
      g_trade.PositionClose(g_pos.Ticket());
   }
}

//+------------------------------------------------------------------+
double CalcLotByDist(double riskDist)
{
   double risk = g_acc.Equity() * InpRiskPct / 100.0;
   if(risk <= 0.0) return 0.0;

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0) return 0.0;

   double ticks  = riskDist / tickSize;
   double lotRaw = risk / (ticks * tickVal);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = MathFloor(lotRaw / lotStep) * lotStep;
   lot = MathMax(minLot, MathMin(lot, maxLot));
   return lot;
}

//+------------------------------------------------------------------+
void OpenLevel1(ENUM_ORDER_TYPE type)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double entry  = (type == ORDER_TYPE_BUY) ? tk.ask : tk.bid;
   double virtDist = pipSize * 1000.0;
   double lot    = CalcLotByDist(virtDist);
   if(lot <= 0.0) return;

   if(InpLog)
      Print(StringFormat(">>> APERTURA LEVEL1 %s lot=%.2f entry=%.5f",
          (type == ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry));

   if(!g_trade.PositionOpen(_Symbol, type, lot, entry, 0.0, 0.0))
   {
      if(InpLog) Print(">>> ERR LEVEL1 retcode=", g_trade.ResultRetcode());
   }
}

//+------------------------------------------------------------------+
void OpenLevel2(ENUM_ORDER_TYPE type)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   double pt    = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double entry = (type == ORDER_TYPE_BUY) ? tk.ask : tk.bid;
   double tp    = (type == ORDER_TYPE_BUY) ? (entry + InpTP_Points * pt)
                                           : (entry - InpTP_Points * pt);
   double riskDist = InpTP_Points * pt;
   double lot   = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   if(InpLog)
      Print(StringFormat(">>> APERTURA LEVEL2 %s lot=%.2f entry=%.5f tp=%.5f",
          (type == ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry, tp));

   if(!g_trade.PositionOpen(_Symbol, type, lot, entry, 0.0, tp))
   {
      if(InpLog) Print(">>> ERR LEVEL2 retcode=", g_trade.ResultRetcode());
      return;
   }
   g_level2Count++;
}

//+------------------------------------------------------------------+
int DetectCrossover()
{
   double l2_1, l1_1, l2_2, l1_2;
   if(!ReadBuf(g_bufLine2, 1, l2_1)) return -1;
   if(!ReadBuf(g_bufLine1, 1, l1_1)) return -1;
   if(!ReadBuf(g_bufLine2, 2, l2_2)) return -1;
   if(!ReadBuf(g_bufLine1, 2, l1_2)) return -1;

   if(l2_1 > l1_1 && l2_2 <= l1_2) return 0;
   if(l2_1 < l1_1 && l2_2 >= l1_2) return 1;
   return -1;
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_ind = iCustom(_Symbol, _Period, InpIndicatorName);
   if(g_ind == INVALID_HANDLE)
   {
      Print("FATAL: iCustom fallito per '", InpIndicatorName, "'");
      return INIT_FAILED;
   }
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);
   g_ready = false;
   g_bar0  = 0;
   g_bufLine1 = MAPeriodToBuf(InpLine1Period);
   g_bufLine2 = MAPeriodToBuf(InpLine2Period);
   g_currentDirection = WRONG_VALUE;
   g_level2Count = 0;

   if(InpLog)
      Print(StringFormat("INIT OK sym=%s tf=%s ind=%s magic=%d risk=%.1f%% "
          "Line1=%s Line2=%s TP=%dpt MaxLevel2=%d",
          _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
          InpIndicatorName, InpMagic, InpRiskPct,
          MAPeriodStr(InpLine1Period), MAPeriodStr(InpLine2Period),
          InpTP_Points, InpMaxLevel2));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   if(InpLog) Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
bool WaitIndicator()
{
   if(g_ready) return true;
   double tmp;
   if(!ReadBuf(BUF_MEDIAN, 1, tmp)) return false;
   g_ready = true;
   if(InpLog) Print("Indicatore pronto");
   return true;
}

//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == 0) return false;
   if(cur == g_bar0) return false;
   g_bar0 = cur;
   return true;
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!WaitIndicator()) return;

   if(!IsNewBar()) return;

   if(InpLog)
      Print(StringFormat("Nuova barra: %s", TimeToString(g_bar0)));

   int sig = DetectCrossover();
   if(sig < 0)
   {
      double l2, l1;
      ReadBuf(g_bufLine2, 1, l2);
      ReadBuf(g_bufLine1, 1, l1);
      if(InpLog)
         Print(StringFormat("Nessun crossover %s=%.5f %s=%.5f",
             MAPeriodStr(InpLine2Period), l2,
             MAPeriodStr(InpLine1Period), l1));
      return;
   }

   ENUM_ORDER_TYPE sigType = (sig == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   string sigStr = (sig == 0) ? "BUY" : "SELL";

   if(InpLog)
      Print(StringFormat(">>> CROSSOVER %s RILEVATO (dir: %s, level2: %d/%d)",
          sigStr,
          (g_currentDirection == WRONG_VALUE ? "NONE" :
           (g_currentDirection == POSITION_TYPE_BUY ? "BUY" : "SELL")),
          g_level2Count, InpMaxLevel2));

   if(g_currentDirection == WRONG_VALUE)
   {
      g_currentDirection = (sig == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
      g_level2Count = 0;
      OpenLevel1(sigType);
      if(InpLog) Print(">>> DIREZIONE IMPOSTATA: ", sigStr);
      return;
   }

   ENUM_ORDER_TYPE currentOrdType = (g_currentDirection == POSITION_TYPE_BUY)
                                    ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;

   if(sigType != currentOrdType)
   {
      if(InpLog) Print(">>> CROSSOVER OPPOSTO - CHIUDO TUTTO");
      CloseAll();
      g_currentDirection = (sig == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
      g_level2Count = 0;
      OpenLevel1(sigType);
      if(InpLog) Print(">>> NUOVA DIREZIONE: ", sigStr);
      return;
   }

   if(g_level2Count < InpMaxLevel2)
   {
      OpenLevel2(sigType);
   }
   else if(InpLog)
   {
      Print(">>> MAX LEVEL2 RAGGIUNTO (", InpMaxLevel2, ")");
   }
}
//+------------------------------------------------------------------+
