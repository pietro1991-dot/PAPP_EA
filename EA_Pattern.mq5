//+------------------------------------------------------------------+
//|                                                     EA_Pattern.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.01"
#property description "Multi-Pattern EA - Fino a 10 pattern configurabili da input"
#property description "Ogni pattern: Entry, Exit, SL, TP, Direction. Tutti in simultanea."
#property description "Linee: 0=Median, 3,7,14,30,121,182,365. Dir: 0=OFF, 1=BUY, 2=SELL"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

input group   "==========  RISK GLOBALE  =========="
input double  InpRiskPct       = 1.0;           // Rischio % per trade
input double  InpLotFixed      = 0.0;           // Lotto fisso (0=usa % rischio)
input int     InpMagic         = 20260623;
input bool    InpLog           = true;

input group   "==========  PATTERN 1 (default: MA3 SELL -> MA121 cross)  =========="
input int     InpP1_Entry      = 3;             // Entry line (0=Med,3,7,14,30,121,182,365)
input int     InpP1_Exit       = 121;           // Exit cross line (0=nessuno)
input int     InpP1_SL         = 0;             // SL line (0=nessuno)
input int     InpP1_TP         = 0;             // TP punti (0=nessuno)
input int     InpP1_Dir        = 2;             // 0=OFF, 1=BUY, 2=SELL

input group   "==========  PATTERN 2 (default: MA7 SELL -> MA121 cross)  =========="
input int     InpP2_Entry      = 7;
input int     InpP2_Exit       = 121;
input int     InpP2_SL         = 0;
input int     InpP2_TP         = 0;
input int     InpP2_Dir        = 2;

input group   "==========  PATTERN 3 (default: MA14 SELL -> MA121 cross)  =========="
input int     InpP3_Entry      = 14;
input int     InpP3_Exit       = 121;
input int     InpP3_SL         = 0;
input int     InpP3_TP         = 0;
input int     InpP3_Dir        = 2;

input group   "==========  PATTERN 4 (default: MA30 SELL -> MA121 cross)  =========="
input int     InpP4_Entry      = 30;
input int     InpP4_Exit       = 121;
input int     InpP4_SL         = 0;
input int     InpP4_TP         = 0;
input int     InpP4_Dir        = 2;

input group   "==========  PATTERN 5 (default: MA365 SELL -> MA7 cross)  =========="
input int     InpP5_Entry      = 365;
input int     InpP5_Exit       = 7;
input int     InpP5_SL         = 0;
input int     InpP5_TP         = 0;
input int     InpP5_Dir        = 2;

input group   "==========  PATTERN 6 (default: MA121 BUY -> MA182 cross)  =========="
input int     InpP6_Entry      = 121;
input int     InpP6_Exit       = 182;
input int     InpP6_SL         = 0;
input int     InpP6_TP         = 0;
input int     InpP6_Dir        = 1;

input group   "==========  PATTERN 7 (default: MA365 BUY -> MA182 cross)  =========="
input int     InpP7_Entry      = 365;
input int     InpP7_Exit       = 182;
input int     InpP7_SL         = 0;
input int     InpP7_TP         = 0;
input int     InpP7_Dir        = 1;

input group   "==========  PATTERN 8 (default: MA365 BUY -> MA121 cross)  =========="
input int     InpP8_Entry      = 365;
input int     InpP8_Exit       = 121;
input int     InpP8_SL         = 0;
input int     InpP8_TP         = 0;
input int     InpP8_Dir        = 1;

input group   "==========  PATTERN 9 (default: MA30 BUY -> SL=MA365 TP=150)  =========="
input int     InpP9_Entry      = 30;
input int     InpP9_Exit       = 0;
input int     InpP9_SL         = 365;
input int     InpP9_TP         = 150;
input int     InpP9_Dir        = 1;

input group   "==========  PATTERN 10 (default: MA7 SELL -> SL=MA365 TP=150)  =========="
input int     InpP10_Entry     = 7;
input int     InpP10_Exit      = 0;
input int     InpP10_SL        = 365;
input int     InpP10_TP        = 150;
input int     InpP10_Dir       = 2;

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

#define MAX_PATTERNS 20

struct Pattern {
   int entry;
   int exit;
   int slLine;
   int tpPt;
   int dir;
};

Pattern  g_patterns[MAX_PATTERNS];
int      g_numPatterns;

int      g_ind;
int      g_indD1;
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
   if(period < 0)  return "OFF";
   return "MA" + IntegerToString(period);
}

string DirStr(int dir)
{
   if(dir == 0) return "OFF";
   if(dir == 1) return "BUY";
   return "SELL";
}

//+------------------------------------------------------------------+
void InitPatterns()
{
   g_numPatterns = 0;

   int e[10] = {InpP1_Entry, InpP2_Entry, InpP3_Entry, InpP4_Entry, InpP5_Entry,
                InpP6_Entry, InpP7_Entry, InpP8_Entry, InpP9_Entry, InpP10_Entry};
   int x[10] = {InpP1_Exit,  InpP2_Exit,  InpP3_Exit,  InpP4_Exit,  InpP5_Exit,
                InpP6_Exit,  InpP7_Exit,  InpP8_Exit,  InpP9_Exit,  InpP10_Exit};
   int s[10] = {InpP1_SL,    InpP2_SL,    InpP3_SL,    InpP4_SL,    InpP5_SL,
                InpP6_SL,    InpP7_SL,    InpP8_SL,    InpP9_SL,    InpP10_SL};
   int t[10] = {InpP1_TP,    InpP2_TP,    InpP3_TP,    InpP4_TP,    InpP5_TP,
                InpP6_TP,    InpP7_TP,    InpP8_TP,    InpP9_TP,    InpP10_TP};
   int d[10] = {InpP1_Dir,    InpP2_Dir,   InpP3_Dir,   InpP4_Dir,   InpP5_Dir,
                InpP6_Dir,    InpP7_Dir,   InpP8_Dir,   InpP9_Dir,   InpP10_Dir};

   for(int i=0; i<10; i++)
   {
      if(d[i] == 0) continue;
      g_patterns[g_numPatterns].entry  = e[i];
      g_patterns[g_numPatterns].exit   = x[i];
      g_patterns[g_numPatterns].slLine = s[i];
      g_patterns[g_numPatterns].tpPt   = t[i];
      g_patterns[g_numPatterns].dir    = d[i];
      g_numPatterns++;
   }

   if(InpLog)
      for(int i=0; i<g_numPatterns; i++)
         Print(StringFormat("  Pattern[%d]: %s %s -> %s%s%s",
            i, MAPeriodStr(g_patterns[i].entry), DirStr(g_patterns[i].dir),
            (g_patterns[i].exit>0?(MAPeriodStr(g_patterns[i].exit)+" cross"):""),
            (g_patterns[i].slLine>0?(" SL="+MAPeriodStr(g_patterns[i].slLine)):""),
            (g_patterns[i].tpPt>0?(" TP="+IntegerToString(g_patterns[i].tpPt)+"pt"):"")));
}

//+------------------------------------------------------------------+
bool IsPriceOk(double v) { return (v > 0.0 && v < 1.0e12); }

//+------------------------------------------------------------------+
bool ReadBufD1(int buf, int d1Shift, double &val)
{
   datetime d1Time = iTime(_Symbol, PERIOD_D1, d1Shift);
   if(d1Time == 0) return false;

   double tmp[1];
   if(g_indD1 != INVALID_HANDLE)
   {
      int copied = CopyBuffer(g_indD1, buf, d1Shift, 1, tmp);
      if(copied == 1 && IsPriceOk(tmp[0])) { val = tmp[0]; return true; }
   }
   int chartShift = iBarShift(_Symbol, _Period, d1Time, false);
   if(chartShift < 0) return false;
   if(CopyBuffer(g_ind, buf, chartShift, 1, tmp) != 1) return false;
   val = tmp[0];
   return IsPriceOk(val);
}

//+------------------------------------------------------------------+
int CheckCrossD1(int buf)
{
   if(buf < 0) return 0;
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
int  g_crossCache[8];

void BuildCrossCache()
{
   for(int b=0; b<8; b++) g_crossCache[b] = CheckCrossD1(b);
}

int CachedCross(int buf)
{
   if(buf < 0 || buf >= 8) return 0;
   return g_crossCache[buf];
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
   return MathMax(minLot, MathMin(lot, maxLot));
}

//+------------------------------------------------------------------+
int GetPatternIndex(ulong ticket)
{
   if(!g_pos.SelectByTicket(ticket)) return -1;
   string cmt = g_pos.Comment();
   if(StringLen(cmt) < 2 || cmt[0] != 'P') return -1;
   return (int)StringToInteger(StringSubstr(cmt, 1));
}

//+------------------------------------------------------------------+
void OpenPatternTrade(int pi)
{
   Pattern &p = g_patterns[pi];
   int cross = CachedCross(MAPeriodToBuf(p.entry));
   if(cross == 0) return;

   int wantDir = -1;
   if(p.dir == 1 && cross == +1) wantDir = 1;
   else if(p.dir == 2 && cross == -1) wantDir = -1;
   else return;

   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double entry  = (wantDir == 1) ? tk.ask : tk.bid;

   double sl = 0.0, tp = 0.0;
   double riskDist = pipSize * 1000.0;

   if(p.tpPt > 0)
   {
      tp = (wantDir == 1) ? entry + p.tpPt * pt : entry - p.tpPt * pt;
      riskDist = p.tpPt * pt;
   }

   double lot = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   string cmt = "P" + IntegerToString(pi);

   if(InpLog)
      Print(StringFormat(">>> APERTURA [%d] %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f %s",
          pi, (wantDir==1?"BUY":"SELL"), lot, entry, sl, tp, cmt));

   if(!g_trade.PositionOpen(_Symbol, (wantDir==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                            lot, entry, sl, tp, cmt))
      if(InpLog) Print(">>> ERR entrata [", pi, "] retcode=", g_trade.ResultRetcode());
}

//+------------------------------------------------------------------+
void CheckPatternExits()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol) continue;
      if(g_pos.Magic() != InpMagic) continue;

      ulong ticket = g_pos.Ticket();
      int pi = GetPatternIndex(ticket);
      if(pi < 0 || pi >= g_numPatterns) continue;

      Pattern &p = g_patterns[pi];
      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      bool shouldClose = false;
      string reason = "";

      if(p.exit > 0)
      {
         int exitCross = CachedCross(MAPeriodToBuf(p.exit));
         int needExit = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(exitCross == needExit) { shouldClose = true; reason = "EXIT " + MAPeriodStr(p.exit) + " cross"; }
      }

      if(!shouldClose && p.slLine > 0)
      {
         int slCross = CachedCross(MAPeriodToBuf(p.slLine));
         int needSL = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(slCross == needSL) { shouldClose = true; reason = "SL " + MAPeriodStr(p.slLine) + " cross"; }
      }

      if(shouldClose)
      {
         if(InpLog) Print(">>> CHIUSO [", pi, "] ", reason, " #", ticket);
         g_trade.PositionClose(ticket);
      }
   }
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_ind = iCustom(_Symbol, _Period, InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_ind == INVALID_HANDLE) { Print("FATAL: iCustom fallito"); return INIT_FAILED; }

   g_indD1 = iCustom(_Symbol, PERIOD_D1, InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_indD1 == INVALID_HANDLE)
      Print("WARNING: g_indD1 fallito - usero' solo chart fallback");

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);

   g_ready  = false;
   g_bar0   = 0;
   g_lastD1Today = 0;

   InitPatterns();

   if(InpLog)
      Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% patterns=%d",
         _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
         InpMagic, InpRiskPct, g_numPatterns));
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
   if(CopyBuffer(g_ind, BUF_MEDIAN, 0, 1, tmp) != 1 || !IsPriceOk(tmp[0])) return false;
   if(InpLog) Print("Indicatore pronto");
   g_ready = true;
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

   BuildCrossCache();

   if(InpLog)
      Print(StringFormat("=== SEGNALE === barra=%s D1=%s pos=%d patterns=%d",
          TimeToString(g_bar0), TimeToString(d1today), PositionsTotal(), g_numPatterns));

   CheckPatternExits();

   for(int pi = 0; pi < g_numPatterns; pi++)
      OpenPatternTrade(pi);
}
//+------------------------------------------------------------------+
