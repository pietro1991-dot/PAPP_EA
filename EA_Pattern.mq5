//+------------------------------------------------------------------+
//|                                                     EA_Pattern.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Pattern EA - Entra su crossover MA D1, esce su crossover MA opposto"
#property description "Basato su pattern_mining.py: MA3/7/14/30/121/182/365/Median"
#property description "Entry: close D1 incrocia linea, Exit: close D1 incrocia linea opposta"
#property description "SL/TP opzionali su linea MA o punti fissi"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

input group   "==========  PATTERN  =========="
input int     InpEntryLine     = 3;             // Linea entrata (3/7/14/30/121/182/365/0=Med)
input int     InpExitLine      = 121;           // Linea uscita
input int     InpDirection     = 0;             // Direzione (0=BOTH, 1=BUY, 2=SELL)

input group   "==========  RISK  =========="
input double  InpRiskPct       = 1.0;           // Rischio % per trade
input double  InpLotFixed      = 0.0;           // Lotto fisso (0=usa % rischio)
input int     InpMagic         = 20260623;
input bool    InpLog           = true;

input group   "==========  STOP LOSS (0=nessuno)  =========="
input int     InpSLLine        = 0;             // SL su linea MA (365=MA365)
input int     InpSLPoints      = 0;             // SL fissa in punti

input group   "==========  TAKE PROFIT (0=nessuno)  =========="
input int     InpTPLine        = 0;             // TP su linea MA
input int     InpTPPoints      = 0;             // TP fisso in punti

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

int      g_ind;
int      g_indD1;
int      g_bufEntry, g_bufExit;
int      g_bufSL, g_bufTP;
datetime g_bar0;
datetime g_lastD1Today;
bool     g_ready;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

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
bool ReadBufD1(int buf, int d1Shift, double &val)
{
   datetime d1Time = iTime(_Symbol, PERIOD_D1, d1Shift);
   if(d1Time == 0) return false;

   double tmp[1];

   if(g_indD1 != INVALID_HANDLE)
   {
      int copied = CopyBuffer(g_indD1, buf, d1Shift, 1, tmp);
      if(copied == 1 && IsPriceOk(tmp[0]))
      {
         val = tmp[0];
         return true;
      }
   }

   int chartShift = iBarShift(_Symbol, _Period, d1Time, false);
   if(chartShift < 0) return false;
   int copied = CopyBuffer(g_ind, buf, chartShift, 1, tmp);
   if(copied != 1) return false;
   val = tmp[0];
   return IsPriceOk(val);
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
void CloseType(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;
      if(g_pos.PositionType() != type)     continue;
      g_trade.PositionClose(g_pos.Ticket());
   }
}

//+------------------------------------------------------------------+
double CalcLotByDist(double riskDist)
{
   if(InpLotFixed > 0.0) return InpLotFixed;

   double risk = g_acc.Equity() * InpRiskPct / 100.0;
   if(risk <= 0.0) return 0.0;

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0) return 0.0;

   double ticks  = riskDist / tickSize;
   if(ticks <= 0.0) ticks = 1000.0;
   double lotRaw = risk / (ticks * tickVal);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = MathFloor(lotRaw / lotStep) * lotStep;
   lot = MathMax(minLot, MathMin(lot, maxLot));
   return lot;
}

//+------------------------------------------------------------------+
// Controlla se l'ultima barra D1 completata ha avuto un crossover
// shift 1 = ultima barra D1 completata, shift 2 = due barre fa
// Ritorna: +1 bullish cross, -1 bearish cross, 0 nessuno
int CheckCrossD1(int buf)
{
   double d1Close2 = iClose(_Symbol, PERIOD_D1, 2);
   double d1Close1 = iClose(_Symbol, PERIOD_D1, 1);
   if(d1Close2 <= 0.0 || d1Close1 <= 0.0) return 0;

   double ma2, ma1;
   if(!ReadBufD1(buf, 2, ma2)) return 0;
   if(!ReadBufD1(buf, 1, ma1)) return 0;

   if(d1Close1 > ma1 && d1Close2 <= ma2) return +1;
   if(d1Close1 < ma1 && d1Close2 >= ma2) return -1;

   return 0;
}

//+------------------------------------------------------------------+
int CountPositions()
{
   int c = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;
      c++;
   }
   return c;
}

//+------------------------------------------------------------------+
bool HasPositionOfType(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;
      if(g_pos.PositionType() == type) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void TryEnter()
{
   int cross = CheckCrossD1(g_bufEntry);
   if(cross == 0) return;

   ENUM_POSITION_TYPE wantType = (cross == +1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;

   bool allowBuy  = (InpDirection == 0 || InpDirection == 1);
   bool allowSell = (InpDirection == 0 || InpDirection == 2);
   if(wantType == POSITION_TYPE_BUY && !allowBuy)  return;
   if(wantType == POSITION_TYPE_SELL && !allowSell) return;

   if(HasPositionOfType(wantType)) return;

   CloseType((wantType == POSITION_TYPE_BUY) ? POSITION_TYPE_SELL : POSITION_TYPE_BUY);
   Sleep(50);

   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double entry  = (wantType == POSITION_TYPE_BUY) ? tk.ask : tk.bid;

   double sl = 0.0, tp = 0.0;
   double riskDist = pipSize * 1000.0;

   if(InpSLLine > 0)
   {
      double slMA = 0.0;
      if(ReadBufD1(g_bufSL, 1, slMA) && IsPriceOk(slMA))
      {
         bool slOk = false;
         if(wantType == POSITION_TYPE_BUY && slMA < entry) { sl = slMA; slOk = true; }
         if(wantType == POSITION_TYPE_SELL && slMA > entry) { sl = slMA; slOk = true; }
         if(slOk) riskDist = MathAbs(entry - sl);
      }
   }
   if(InpSLPoints > 0)
   {
      double slFix = (wantType == POSITION_TYPE_BUY)
         ? entry - InpSLPoints * pt
         : entry + InpSLPoints * pt;
      if(sl == 0.0)
      {
         sl = slFix;
         riskDist = InpSLPoints * pt;
      }
      else
      {
         double fixDist = MathAbs(entry - slFix);
         double curDist = MathAbs(entry - sl);
         if(fixDist < curDist)
         {
            sl = slFix;
            riskDist = fixDist;
         }
      }
   }

   if(InpTPLine > 0)
   {
      double tpMA = 0.0;
      if(ReadBufD1(g_bufTP, 1, tpMA) && IsPriceOk(tpMA))
      {
         bool tpOk = false;
         if(wantType == POSITION_TYPE_BUY && tpMA > entry) { tp = tpMA; tpOk = true; }
         if(wantType == POSITION_TYPE_SELL && tpMA < entry) { tp = tpMA; tpOk = true; }
      }
   }
   if(InpTPPoints > 0 && tp == 0.0)
      tp = (wantType == POSITION_TYPE_BUY)
         ? entry + InpTPPoints * pt
         : entry - InpTPPoints * pt;

   double lot = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   if(InpLog)
      Print(StringFormat(">>> APERTURA %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f risk=%.0fpt",
          (wantType == POSITION_TYPE_BUY ? "BUY" : "SELL"),
          lot, entry, sl, tp, riskDist / pt));

   if(!g_trade.PositionOpen(_Symbol, wantType, lot, entry, sl, tp))
   {
      if(InpLog) Print(">>> ERR entrata retcode=", g_trade.ResultRetcode());
   }
}

//+------------------------------------------------------------------+
void CheckExits()
{
   int cross = CheckCrossD1(g_bufExit);
   if(cross == 0) return;

   ENUM_POSITION_TYPE exitType = (cross == +1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

      // Exit se la direzione del crossover e' opposta alla posizione
      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      if(posType == POSITION_TYPE_BUY && exitType == POSITION_TYPE_SELL)
      {
         if(InpLog) Print(">>> USCITA BUY (bearish cross) #" + IntegerToString(g_pos.Ticket()));
         g_trade.PositionClose(g_pos.Ticket());
      }
      else if(posType == POSITION_TYPE_SELL && exitType == POSITION_TYPE_BUY)
      {
         if(InpLog) Print(">>> USCITA SELL (bullish cross) #" + IntegerToString(g_pos.Ticket()));
         g_trade.PositionClose(g_pos.Ticket());
      }
   }
}

//+------------------------------------------------------------------+
void CheckSLCross()
{
   if(InpSLLine <= 0) return;

   int cross = CheckCrossD1(g_bufSL);
   if(cross == 0) return;

   ENUM_POSITION_TYPE slType = (cross == +1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      bool hitSL = false;
      if(posType == POSITION_TYPE_BUY && slType == POSITION_TYPE_SELL) hitSL = true;
      if(posType == POSITION_TYPE_SELL && slType == POSITION_TYPE_BUY) hitSL = true;

      if(hitSL)
      {
         if(InpLog) Print(">>> SL LINEA #" + IntegerToString(g_pos.Ticket()));
         g_trade.PositionClose(g_pos.Ticket());
      }
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_ind = iCustom(_Symbol, _Period, InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_ind == INVALID_HANDLE)
   {
      Print("FATAL: iCustom fallito per '", InpIndicatorName, "'");
      return INIT_FAILED;
   }
   g_indD1 = iCustom(_Symbol, PERIOD_D1, InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_indD1 == INVALID_HANDLE)
      Print("WARNING: g_indD1 fallito - usero' solo chart fallback");

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);

   g_bufEntry = MAPeriodToBuf(InpEntryLine);
   g_bufExit  = MAPeriodToBuf(InpExitLine);
   g_bufSL    = (InpSLLine > 0)  ? MAPeriodToBuf(InpSLLine)  : -1;
   g_bufTP    = (InpTPLine > 0)  ? MAPeriodToBuf(InpTPLine)  : -1;

   g_ready  = false;
   g_bar0   = 0;
   g_lastD1Today = 0;

   if(InpLog)
      Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% "
          "Entry=%s Exit=%s Dir=%s SL=%s%d TP=%s%d",
         _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
         InpMagic, InpRiskPct,
         MAPeriodStr(InpEntryLine), MAPeriodStr(InpExitLine),
         (InpDirection==0?"BOTH":(InpDirection==1?"BUY":"SELL")),
         (InpSLLine>0?MAPeriodStr(InpSLLine)+" ":"OFF "), InpSLPoints,
         (InpTPLine>0?MAPeriodStr(InpTPLine)+" ":"OFF "), InpTPPoints));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   if(g_indD1 != INVALID_HANDLE) IndicatorRelease(g_indD1);
   if(InpLog) Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
bool WaitIndicator()
{
   if(g_ready) return true;
   double tmp[1];
   if(CopyBuffer(g_ind, BUF_MEDIAN, 0, 1, tmp) != 1 || !IsPriceOk(tmp[0]))
      return false;
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

   datetime d1today = iTime(_Symbol, PERIOD_D1, 0);
   if(d1today == 0)             return;
   if(d1today == g_lastD1Today) return;
   g_lastD1Today = d1today;

   int posCount = CountPositions();

   if(InpLog)
      Print(StringFormat("=== SEGNALE === barra=%s D1=%s posizioni=%d Entry=%s Exit=%s",
          TimeToString(g_bar0), TimeToString(d1today), posCount,
          MAPeriodStr(InpEntryLine), MAPeriodStr(InpExitLine)));

   int entryCross = CheckCrossD1(g_bufEntry);
   int exitCross  = CheckCrossD1(g_bufExit);

   if(InpLog)
   {
      string entryStr = (entryCross==0?"NESSUNO":(entryCross>0?"BUY":"SELL"));
      string exitStr  = (exitCross ==0?"NESSUNO":(exitCross >0?"BUY":"SELL"));
      Print(StringFormat("   entry=%s exit=%s", entryStr, exitStr));
   }

   CheckSLCross();

   if(posCount > 0)
   {
      ENUM_POSITION_TYPE posType = WRONG_VALUE;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(g_pos.SelectByIndex(i) && g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol)
         {
            posType = g_pos.PositionType();
            break;
         }
      }

      if(posType != WRONG_VALUE)
      {
         int exitDir = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(exitCross == exitDir)
         {
            if(InpLog) Print(StringFormat("   => EXIT %s cross opposto",
                (posType == POSITION_TYPE_BUY) ? "BUY" : "SELL"));
            CloseAll();
            return;
         }

         // Gia' in posizione, nessuna nuova entrata nella stessa direzione
         if(entryCross != 0)
         {
            ENUM_POSITION_TYPE entryDir = (entryCross == +1) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
            if(entryDir == posType)
            {
               if(InpLog) Print("   => ENTRY STESSA DIR - gia' in posizione");
               return;
            }
         }
         return;
      }
   }

   if(entryCross != 0)
      TryEnter();
   else if(InpLog && posCount == 0)
      Print("   => NESSUN ENTRY CROSS - attesa...");
}
//+------------------------------------------------------------------+
