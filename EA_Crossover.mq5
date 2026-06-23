//+------------------------------------------------------------------+
//|                                                 EA_Crossover.mq5 |
//|                                                        PaPP v2   |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.10"
#property description "EA Crossover - Entry/Exit lines separati, flip su exit crossover"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

input group   "==========  ENTRY CROSSOVER  =========="
input int     InpEntryLine1    = 365;
input int     InpEntryLine2    = 121;

input group   "==========  EXIT CROSSOVER  =========="
input int     InpExitLine1     = 365;
input int     InpExitLine2     = 121;

input group   "==========  RISK / TP  =========="
input double  InpRiskPct       = 1.0;
input int     InpTP_Points     = 50;
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

int      g_ind;      // chart timeframe handle
int      g_indD1;    // D1 timeframe handle
int      g_bufEntry1, g_bufEntry2;
int      g_bufExit1,  g_bufExit2;
datetime g_bar0;
datetime g_lastD1Today;
bool     g_ready;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

ENUM_POSITION_TYPE g_currentDirection;

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

   // D1 handle: CopyBuffer(handle, buf, d1Shift, 1, tmp) con AS_SERIES
   // start_pos = shift dal presente (0=oggi, 1=ieri, 2=2gg fa)
   if(g_indD1 != INVALID_HANDLE)
   {
      int copied = CopyBuffer(g_indD1, buf, d1Shift, 1, tmp);
      if(copied == 1 && IsPriceOk(tmp[0]))
      {
         val = tmp[0];
         if(InpLog)
            Print(StringFormat("   DEBUG ReadBufD1(D1) buf=%d shift=%d val=%.5f",
                buf, d1Shift, val));
         return true;
      }
   }

   // Fallback chart handle
   int chartShift = iBarShift(_Symbol, _Period, d1Time, false);
   if(chartShift < 0) return false;
   int copied = CopyBuffer(g_ind, buf, chartShift, 1, tmp);
   if(copied != 1) return false;
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

   // Cap lot to avoid margin blowout
   double marginPerLot = 0;
   if(SymbolInfoDouble(_Symbol, SYMBOL_MARGIN_INITIAL, marginPerLot) && marginPerLot > 0)
   {
       double maxLot = g_acc.FreeMargin() / marginPerLot * 0.3;
       if(lot > maxLot)
       {
           if(InpLog)
               Print(StringFormat(">>> LEVEL2 lot capped: %.2f -> %.2f (margin=%.2f perLot=%.2f)",
                   lot, maxLot, g_acc.FreeMargin(), marginPerLot));
           lot = MathMax(maxLot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
       }
   }

   if(InpLog)
      Print(StringFormat(">>> APERTURA LEVEL2 %s lot=%.2f entry=%.5f tp=%.5f",
          (type == ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry, tp));

   if(!g_trade.PositionOpen(_Symbol, type, lot, entry, 0.0, tp))
   {
      if(InpLog) Print(">>> ERR LEVEL2 retcode=", g_trade.ResultRetcode());
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
      Print("WARNING: g_indD1 (D1 handle) fallito - usero' solo chart fallback");
   else if(InpLog)
      Print("D1 handle OK");

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);
   g_ready = false;
   g_bar0  = 0;
   g_lastD1Today = 0;
   g_bufEntry1 = MAPeriodToBuf(InpEntryLine1);
   g_bufEntry2 = MAPeriodToBuf(InpEntryLine2);
   g_bufExit1  = MAPeriodToBuf(InpExitLine1);
   g_bufExit2  = MAPeriodToBuf(InpExitLine2);
   g_currentDirection = WRONG_VALUE;

   if(InpLog)
      Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% "
          "Entry=%s/%s Exit=%s/%s TP=%dpt",
          _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
          InpMagic, InpRiskPct,
          MAPeriodStr(InpEntryLine1), MAPeriodStr(InpEntryLine2),
          MAPeriodStr(InpExitLine1),  MAPeriodStr(InpExitLine2),
           InpTP_Points));
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
   if(d1today == 0)              return;
   if(d1today == g_lastD1Today)  return;
   g_lastD1Today = d1today;

   // --- SINCRONIZZA DIREZIONE DALLE POSIZIONI REALI ---
   ENUM_POSITION_TYPE realDir = WRONG_VALUE;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(g_pos.SelectByIndex(i) && g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol)
      {
         realDir = g_pos.PositionType();
         break;
      }
   }
   if(realDir != g_currentDirection)
   {
      string oldS = (g_currentDirection==WRONG_VALUE)?"NONE":(g_currentDirection==POSITION_TYPE_BUY?"BUY":"SELL");
      string newS = (realDir==WRONG_VALUE)?"NONE":(realDir==POSITION_TYPE_BUY?"BUY":"SELL");
      if(InpLog) Print(StringFormat("   Sincronizzazione direzione: %s -> %s", oldS, newS));
      g_currentDirection = realDir;
   }

   // --- LOG COMPLETO STATO ---
   string dirStr;
   if(g_currentDirection == WRONG_VALUE) dirStr = "NONE";
   else if(g_currentDirection == POSITION_TYPE_BUY) dirStr = "BUY";
   else dirStr = "SELL";
   if(InpLog)
       Print(StringFormat("=== SEGNALE === barra=%s D1=%s direzione=%s posizioni=%d",
           TimeToString(g_bar0), TimeToString(d1today), dirStr, PositionsTotal()));

   // --- CROSSOVER ENTRY ---
   double ef1, es1, ef2, es2;
   int entrySig = -1;
   if(ReadBufD1(g_bufEntry2, 1, ef1) && ReadBufD1(g_bufEntry1, 1, es1) &&
      ReadBufD1(g_bufEntry2, 2, ef2) && ReadBufD1(g_bufEntry1, 2, es2))
   {
      if(ef1 > es1 && ef2 <= es2) entrySig = 0;
      else if(ef1 < es1 && ef2 >= es2) entrySig = 1;
      if(InpLog)
         Print(StringFormat("   ENTRY %s[1]=%.5f %s[1]=%.5f | %s[2]=%.5f %s[2]=%.5f -> %s",
             MAPeriodStr(InpEntryLine2), ef1, MAPeriodStr(InpEntryLine1), es1,
             MAPeriodStr(InpEntryLine2), ef2, MAPeriodStr(InpEntryLine1), es2,
             entrySig<0 ? "NESSUN CROSS" : (entrySig==0 ? "CROSS BUY" : "CROSS SELL")));
   }
   else if(InpLog)
      Print(StringFormat("   ENTRY %s/%s: LETTURA FALLITA",
          MAPeriodStr(InpEntryLine2), MAPeriodStr(InpEntryLine1)));

   // --- CROSSOVER EXIT ---
   double xf1, xs1, xf2, xs2;
   int exitSig = -1;
   if(ReadBufD1(g_bufExit2, 1, xf1) && ReadBufD1(g_bufExit1, 1, xs1) &&
      ReadBufD1(g_bufExit2, 2, xf2) && ReadBufD1(g_bufExit1, 2, xs2))
   {
      if(xf1 > xs1 && xf2 <= xs2) exitSig = 0;
      else if(xf1 < xs1 && xf2 >= xs2) exitSig = 1;
      if(InpLog)
         Print(StringFormat("   EXIT  %s[1]=%.5f %s[1]=%.5f | %s[2]=%.5f %s[2]=%.5f -> %s",
             MAPeriodStr(InpExitLine2), xf1, MAPeriodStr(InpExitLine1), xs1,
             MAPeriodStr(InpExitLine2), xf2, MAPeriodStr(InpExitLine1), xs2,
             exitSig<0 ? "NESSUN CROSS" : (exitSig==0 ? "CROSS BUY" : "CROSS SELL")));
   }
   else if(InpLog)
      Print(StringFormat("   EXIT  %s/%s: LETTURA FALLITA",
          MAPeriodStr(InpExitLine2), MAPeriodStr(InpExitLine1)));

   // --- NONE: entry crossover apre Level 1 ---
   if(g_currentDirection == WRONG_VALUE)
   {
      if(entrySig < 0)
      {
         if(InpLog) Print("   => NESSUN ENTRY CROSS - attesa...");
         return;
      }
      ENUM_ORDER_TYPE t = (entrySig == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      g_currentDirection = (entrySig == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
      if(InpLog) Print(StringFormat("   => ENTRY NONE -> %s (Level 1)", entrySig==0?"BUY":"SELL"));
      OpenLevel1(t);
      return;
   }

   ENUM_ORDER_TYPE curType = (g_currentDirection == POSITION_TYPE_BUY)
                             ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;

   // --- Exit crossover opposto: flip direzionale ---
   if(exitSig >= 0)
   {
      ENUM_ORDER_TYPE exitType = (exitSig == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(exitType != curType)
      {
         if(InpLog) Print(StringFormat("   => EXIT CROSS OPPOSTO (cur=%s exit=%s) - FLIP",
             curType==ORDER_TYPE_BUY?"BUY":"SELL", exitType==ORDER_TYPE_BUY?"BUY":"SELL"));
         CloseAll();
         g_currentDirection = (exitSig == 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
         OpenLevel1(exitType);
         curType = exitType;
         if(InpLog) Print(StringFormat("   => FLIP -> %s (Level 1)", exitSig==0?"BUY":"SELL"));
      }
      else if(InpLog)
         Print(StringFormat("   => EXIT CROSS STESSA DIREZIONE (cur=%s) - ignorato",
             curType==ORDER_TYPE_BUY?"BUY":"SELL"));
   }
   else if(InpLog && g_currentDirection != WRONG_VALUE)
      Print(StringFormat("   => NO EXIT CROSS (cur=%s) - si cerca entry Level 2",
          curType==ORDER_TYPE_BUY?"BUY":"SELL"));

   // --- Entry crossover stessa direzione: Level 2 ---
   if(entrySig >= 0)
   {
      ENUM_ORDER_TYPE entryType = (entrySig == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(entryType == curType)
      {
         if(InpLog) Print(StringFormat("   => ENTRY CROSS STESSA DIR -> Level 2 %s",
             entryType==ORDER_TYPE_BUY?"BUY":"SELL"));
         OpenLevel2(entryType);
      }
      else if(InpLog)
         Print(StringFormat("   => ENTRY CROSS OPPOSTO (cur=%s entry=%s) - ignorato (exit gestisce flip)",
             curType==ORDER_TYPE_BUY?"BUY":"SELL", entryType==ORDER_TYPE_BUY?"BUY":"SELL"));
   }
   else if(InpLog && g_currentDirection != WRONG_VALUE)
      Print("   => NO ENTRY CROSS - fine elaborazione");
}
//+------------------------------------------------------------------+
