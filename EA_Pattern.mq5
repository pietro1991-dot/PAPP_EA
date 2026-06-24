//+------------------------------------------------------------------+
//|                                                     EA_Pattern.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.00"
#property description "Multi-Pattern EA - TUTTI i pattern da pattern_mining.py in simultanea"
#property description "9 pattern simultanei: entry/exit cross + SL/TP. Ogni pattern ha la sua logica."
#property description "Basato su analisi: MA3/7/14/30/121/182/365/Median + SL=MA365 + TP fisso"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

input group   "==========  RISK GLOBALE  =========="
input double  InpRiskPct       = 1.0;           // Rischio % per trade
input double  InpLotFixed      = 0.0;           // Lotto fisso per pattern (0=usa %)
input int     InpMagic         = 20260623;
input bool    InpLog           = true;

input group   "==========  SPREAD (solo log)  =========="
input int     InpSpreadPt      = 15;            // Spread stimato in punti (log)

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
   int   entry;       // MA line for entry cross
   int   exit;        // MA line for exit cross (0=nessuno)
   int   slLine;      // MA line for SL dynamic check (0=nessuno)
   int   tpPt;        // TP in punti (0=nessuno)
   int   dir;         // 1=BUY, 2=SELL
};

Pattern g_patterns[MAX_PATTERNS];
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
   return "MA" + IntegerToString(period);
}

string DirStr(int dir) { return (dir==1)?"BUY":"SELL"; }

//+------------------------------------------------------------------+
void InitPatterns()
{
   g_numPatterns = 0;

   // Pattern da Analisi 2: entry su cross, exit su cross opposto
   // (entry, exit, slLine, tpPt, dir)

   // --- SELL patterns (entrate ribassiste) ---
   g_patterns[g_numPatterns++] = {3,   121, 0, 0, 2};  // MA3 SELL -> MA121 cross  (Sharpe 2.07, 1060t)
   g_patterns[g_numPatterns++] = {7,   121, 0, 0, 2};  // MA7 SELL -> MA121 cross  (Sharpe 2.09, 544t)
   g_patterns[g_numPatterns++] = {14,  121, 0, 0, 2};  // MA14 SELL -> MA121 cross (Sharpe 1.61, 363t)
   g_patterns[g_numPatterns++] = {30,  121, 0, 0, 2};  // MA30 SELL -> MA121 cross (Sharpe 2.64, 245t)
   g_patterns[g_numPatterns++] = {365, 7,   0, 0, 2};  // MA365 SELL -> MA7 cross  (Sharpe 3.35, 60t)

   // --- BUY patterns (entrate rialziste) ---
   g_patterns[g_numPatterns++] = {121, 182, 0, 0, 1};  // MA121 BUY -> MA182 cross  (Sharpe 2.20, 118t)
   g_patterns[g_numPatterns++] = {365, 182, 0, 0, 1};  // MA365 BUY -> MA182 cross  (Sharpe 1.51, 55t)
   g_patterns[g_numPatterns++] = {365, 121, 0, 0, 1};  // MA365 BUY -> MA121 cross  (Sharpe 1.08, 56t)

   // Pattern da Analisi 3: SL su MA365 + TP fisso
   g_patterns[g_numPatterns++] = {30,  0,   365, 150, 1}; // MA30 BUY -> SL=MA365 TP=150 (Sharpe 8.77)
   g_patterns[g_numPatterns++] = {7,   0,   365, 150, 2}; // MA7 SELL -> SL=MA365 TP=150 (Sharpe 2.98)

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
// Cache dei cross per tutte le linee usate
int g_crossCache[8]; // indici 0-7 corrispondono ai buffer

void BuildCrossCache()
{
   for(int b=0; b<8; b++)
      g_crossCache[b] = CheckCrossD1(b);
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
void CloseTicket(ulong ticket)
{
   g_trade.PositionClose(ticket);
}

//+------------------------------------------------------------------+
void OpenPatternTrade(int pi)
{
   Pattern &p = g_patterns[pi];
   int cross = CachedCross(MAPeriodToBuf(p.entry));
   if(cross == 0) return;

   // Determine direction from pattern
   int wantDir = -1; // 1=BUY, -1=SELL
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

   // TP fisso
   if(p.tpPt > 0)
   {
      tp = (wantDir == 1) ? entry + p.tpPt * pt : entry - p.tpPt * pt;
      riskDist = p.tpPt * pt;
   }

   // SL fisso (usa InpSLPoints se > 0, altrimenti la distanza di rischio usa il TP o virtuale)
   // Per pattern con SL su linea (slLine>0), NON settiamo SL fixed (dynamic check)

   double lot = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   string cmt = "P" + IntegerToString(pi);

   if(InpLog)
      Print(StringFormat(">>> APERTURA [%d] %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f %s",
          pi, (wantDir==1?"BUY":"SELL"), lot, entry, sl, tp, cmt));

   if(!g_trade.PositionOpen(_Symbol, (wantDir==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                            lot, entry, sl, tp, cmt))
   {
      if(InpLog) Print(">>> ERR entrata [", pi, "] retcode=", g_trade.ResultRetcode());
   }
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

      // Exit cross: direzione opposta sulla linea di uscita
      if(p.exit > 0)
      {
         int exitCross = CachedCross(MAPeriodToBuf(p.exit));
         int needExit = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(exitCross == needExit)
         {
            shouldClose = true;
            reason = "EXIT " + MAPeriodStr(p.exit) + " cross";
         }
      }

      // SL su linea: stessa direzione = colpito
      if(!shouldClose && p.slLine > 0)
      {
         int slCross = CachedCross(MAPeriodToBuf(p.slLine));
         int needSL = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(slCross == needSL)
         {
            shouldClose = true;
            reason = "SL " + MAPeriodStr(p.slLine) + " cross";
         }
      }

      if(shouldClose)
      {
         if(InpLog) Print(">>> CHIUSO [", pi, "] ", reason, " #", ticket);
         CloseTicket(ticket);
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

   // Costruisce cache dei cross per TUTTE le linee
   BuildCrossCache();

   if(InpLog)
      Print(StringFormat("=== SEGNALE === barra=%s D1=%s pos=%d pattern=%d",
          TimeToString(g_bar0), TimeToString(d1today), PositionsTotal(), g_numPatterns));

   // --- EXIT: controlla ogni posizione aperta contro il suo pattern ---
   CheckPatternExits();

   // --- ENTRY: controlla ogni pattern per nuovi ingressi ---
   for(int pi = 0; pi < g_numPatterns; pi++)
      OpenPatternTrade(pi);
}
//+------------------------------------------------------------------+
