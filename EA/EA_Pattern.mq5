//+------------------------------------------------------------------+
//|                                                     EA_Pattern.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.05"
#property description "Multi-Pattern EA - Fino a 10 pattern configurabili da input"
#property description "Ogni pattern: Entry, Exit, SL, TP, Direction. Tutti in simultanea."
#property description "Linee: 0=Median, 3,7,14,30,121,182,365. Dir: 0=OFF, 1=BUY, 2=SELL"
#property description "Pattern default da ANALISI 3: entry cross + SL dinamico sulla linea + TP fisso"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

//==========  RISK GLOBALE  ==========
input double  InpRiskPct       = 1.0;           // Rischio % per trade
input double  InpLotFixed      = 0.0;           // Lotto fisso (0=usa % rischio)
input double  InpMaxLot        = 0.0;           // Lotto massimo assoluto (0=usa broker)
input int     InpMaxSpread     = 50;            // Spread massimo in punti (0=disabilita)
input int     InpMinSLDistPts  = 50;            // Distanza SL minima in punti
input double  InpFallbackRiskPips = 100.0;      // Risk distance in pips quando il pattern non ha SL (per sizing)
input int     InpMaxPos        = 20;            // Max posizioni totali (0=illimitato)
input int     InpMaxPerPattern = 1;             // Max posizioni per pattern (0=illimitato)
input int     InpMagic         = 20260623;
input string  InpLogFile       = "papp_ea_log.jsonl"; // File log decisioni (vuoto=disabilita)
input int     InpMarketInterval = 300;           // Intervallo market snapshot secondi (0=disabilita)
input bool    InpLog           = true;

// Pattern da ANALISI 3 (Entry cross + SL dinamico su linea + TP fisso).
// SOLO pattern validati out-of-sample (train <=2020, test >2020), ordinati
// per Sharpe per-trade nel test set. Sharpe corretto (per-trade) + costi
// (spread+commissione) + niente look-ahead. I pattern deboli/negativi OOS
// (MA14 SELL TP30, MA182 SELL TP60, MA121 SELL TP80) sono stati rimossi.
// Linee: 0=Med,3,7,14,30,121,182,365. Dir: 0=OFF, 1=BUY, 2=SELL. Exit=0.

//==========  PATTERN 1 (MA30 SELL, SL=MA365, TP=150 | OOS Win95% Sh1.96)  =========="
input int     InpP1_Entry      = 30;            // Entry line (0=Med,3,7,14,30,121,182,365)
input int     InpP1_Exit       = 0;             // Exit cross line (0=nessuno)
input int     InpP1_SL         = 365;           // SL line (0=nessuno)
input int     InpP1_TP         = 150;           // TP punti (0=nessuno)
input int     InpP1_Dir        = 2;             // 0=OFF, 1=BUY, 2=SELL

//==========  PATTERN 2 (MA121 BUY, SL=MA365, TP=150 | OOS Win89% Sh1.07)  =========="
input int     InpP2_Entry      = 121;
input int     InpP2_Exit       = 0;
input int     InpP2_SL         = 365;
input int     InpP2_TP         = 150;
input int     InpP2_Dir        = 1;

//==========  PATTERN 3 (MA365 SELL, SL=MA121, TP=120 | OOS Win89% Sh0.38)  =========="
input int     InpP3_Entry      = 365;
input int     InpP3_Exit       = 0;
input int     InpP3_SL         = 121;
input int     InpP3_TP         = 120;
input int     InpP3_Dir        = 2;

//==========  PATTERN 4 (MA7 SELL, SL=MA365, TP=120 | OOS Win93% Sh0.24)  =========="
input int     InpP4_Entry      = 7;
input int     InpP4_Exit       = 0;
input int     InpP4_SL         = 365;
input int     InpP4_TP         = 120;
input int     InpP4_Dir        = 2;

//==========  PATTERN 5 (MA30 BUY, SL=MA365, TP=150 | OOS Win90% Sh0.23)  =========="
input int     InpP5_Entry      = 30;
input int     InpP5_Exit       = 0;
input int     InpP5_SL         = 365;
input int     InpP5_TP         = 150;
input int     InpP5_Dir        = 1;

//==========  PATTERN 6 (MA14 BUY, SL=MA365, TP=150 | OOS Win94% Sh0.17)  =========="
input int     InpP6_Entry      = 14;
input int     InpP6_Exit       = 0;
input int     InpP6_SL         = 365;
input int     InpP6_TP         = 150;
input int     InpP6_Dir        = 1;

//==========  PATTERN 7 (OFF - escluso: debole OOS)  =========="
input int     InpP7_Entry      = 14;
input int     InpP7_Exit       = 0;
input int     InpP7_SL         = 365;
input int     InpP7_TP         = 30;
input int     InpP7_Dir        = 0;

//==========  PATTERN 8 (OFF - escluso: debole OOS)  =========="
input int     InpP8_Entry      = 182;
input int     InpP8_Exit       = 0;
input int     InpP8_SL         = 365;
input int     InpP8_TP         = 60;
input int     InpP8_Dir        = 0;

//==========  PATTERN 9 (OFF - escluso: Sharpe ~0 OOS, campione piccolo)  =========="
input int     InpP9_Entry      = 121;
input int     InpP9_Exit       = 0;
input int     InpP9_SL         = 365;
input int     InpP9_TP         = 80;
input int     InpP9_Dir        = 0;

//==========  PATTERN 10 (OFF - libero per test)  =========="
input int     InpP10_Entry     = 7;
input int     InpP10_Exit      = 0;
input int     InpP10_SL        = 365;
input int     InpP10_TP        = 150;
input int     InpP10_Dir       = 0;

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
int      g_logHandle = -1;
datetime g_lastMarketLog;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

struct PosSnapshot {
   ulong ticket;
   double entry;
   double sl;
   double tp;
   int type;
   int pattern;
};
PosSnapshot g_prevPos[100];
int g_prevCount;

void SavePosSnapshot()
{
   g_prevCount = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol) continue;
      if(g_pos.Magic() != InpMagic) continue;
      if(g_prevCount >= 100) break;
      g_prevPos[g_prevCount].ticket  = g_pos.Ticket();
      g_prevPos[g_prevCount].entry   = g_pos.PriceOpen();
      g_prevPos[g_prevCount].sl      = g_pos.StopLoss();
      g_prevPos[g_prevCount].tp      = g_pos.TakeProfit();
      g_prevPos[g_prevCount].type    = (int)g_pos.PositionType();
      g_prevPos[g_prevCount].pattern = GetPatternIndex(g_pos.Ticket());
      g_prevCount++;
   }
}

void LogBrokerCloses()
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   for(int i = g_prevCount - 1; i >= 0; i--)
   {
      ulong t = g_prevPos[i].ticket;
      // Check if this ticket still exists
      if(g_pos.SelectByTicket(t)) continue;

      // Position is gone — closed by broker (TP/SL/StopOut)
      PosSnapshot p = g_prevPos[i];
      double exitPr = (p.type == (int)POSITION_TYPE_BUY) ? tk.bid : tk.ask;
      double pnlPt = (p.type == (int)POSITION_TYPE_BUY) ?
         (exitPr - p.entry) / _Point : (p.entry - exitPr) / _Point;
      string dirStr = (p.type == (int)POSITION_TYPE_BUY) ? "BUY" : "SELL";

      // Determine reason: TP, SL, or stop out
      string reason = "";
      if(p.tp > 0.0)
      {
         bool tpHit = (p.type == (int)POSITION_TYPE_BUY && tk.bid >= p.tp) ||
                      (p.type == (int)POSITION_TYPE_SELL && tk.ask <= p.tp);
         if(tpHit) reason = "TP target hit";
      }
      if(reason == "" && p.sl > 0.0)
      {
         bool slHit = (p.type == (int)POSITION_TYPE_BUY && tk.bid <= p.sl) ||
                      (p.type == (int)POSITION_TYPE_SELL && tk.ask >= p.sl);
         if(slHit) reason = "SL stop hit";
      }
      if(reason == "") reason = "Stop out / forced close";

      if(InpLog)
         Print(">>> BROKER CLOSE [", p.pattern, "] ", reason, " pnl=", DoubleToString(pnlPt,1), "pt #", t);
      LogDecision("close", p.pattern, dirStr, reason, p.entry, p.sl, p.tp, 0, exitPr, pnlPt);
   }
}

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
   return -1;
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

      // Validazione linee
      if(MAPeriodToBuf(e[i]) < 0) { Print("WARNING: Pattern ", i+1, " entry line ", e[i], " invalida"); continue; }
      if(x[i] > 0 && MAPeriodToBuf(x[i]) < 0) { Print("WARNING: Pattern ", i+1, " exit line ", x[i], " invalida"); continue; }
      if(s[i] > 0 && MAPeriodToBuf(s[i]) < 0) { Print("WARNING: Pattern ", i+1, " SL line ", s[i], " invalida"); continue; }

      g_patterns[g_numPatterns].entry  = e[i];
      g_patterns[g_numPatterns].exit   = x[i];
      g_patterns[g_numPatterns].slLine = s[i];
      g_patterns[g_numPatterns].tpPt   = t[i];
      g_patterns[g_numPatterns].dir    = d[i];
      g_numPatterns++;
   }

   if(g_numPatterns == 0)
      Print("ATTENZIONE: Nessun pattern attivo! Imposta Dir>0 per almeno un pattern.");

   if(InpLog)
   {
      Print("NOTA: Exit/SL verificati solo a chiusura D1. Senza hard SL, gap intraday non coperti.");
      for(int i=0; i<g_numPatterns; i++)
         Print(StringFormat("  Pattern[%d]: %s %s -> %s%s%s",
            i, MAPeriodStr(g_patterns[i].entry), DirStr(g_patterns[i].dir),
            (g_patterns[i].exit>0?(MAPeriodStr(g_patterns[i].exit)+" cross"):""),
            (g_patterns[i].slLine>0?(" SL="+MAPeriodStr(g_patterns[i].slLine)):""),
            (g_patterns[i].tpPt>0?(" TP="+IntegerToString(g_patterns[i].tpPt)+"pt"):"")));
   }
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
   int periods[8] = {0, 365, 182, 121, 30, 14, 7, 3};
   string log = "";
   for(int b=0; b<8; b++)
   {
      g_crossCache[b] = CheckCrossD1(b);
      if(InpLog && g_crossCache[b] != 0)
      {
         if(log != "") log += ", ";
         log += MAPeriodStr(periods[b]) + "=" + IntegerToString(g_crossCache[b]);
      }
   }
   if(InpLog && log != "")
      Print("   Cross attivi: ", log);
}

int CachedCross(int buf)
{
   if(buf < 0 || buf >= 8) return 0;
   return g_crossCache[buf];
}

//+------------------------------------------------------------------+
double CalcLotByDist(double riskDist)
{
   if(InpLotFixed > 0.0)
      return (InpMaxLot > 0.0) ? MathMin(InpLotFixed, InpMaxLot) : InpLotFixed;
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
   double brokerMax = (InpMaxLot > 0.0) ? MathMin(maxLot, InpMaxLot) : maxLot;
   return MathMax(minLot, MathMin(lot, brokerMax));
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
void LogDecision(string action, int pi, string dir, string reason,
                 double entry=0.0, double sl=0.0, double tp=0.0,
                 double lot=0.0, double exitPrice=0.0, double pnl=0.0)
{
   if(g_logHandle < 0) return;
   string json = StringFormat(
      "{\"t\":%d,\"action\":\"%s\",\"pattern\":%d,\"dir\":\"%s\"",
      (int)TimeCurrent(), action, pi, dir);
   if(StringLen(reason) > 0) json += ",\"reason\":\"" + reason + "\"";
   if(entry > 0.0)    json += StringFormat(",\"entry\":%.5f", entry);
   if(sl > 0.0)       json += StringFormat(",\"sl\":%.5f", sl);
   if(tp > 0.0)       json += StringFormat(",\"tp\":%.5f", tp);
   if(lot > 0.0)      json += StringFormat(",\"lot\":%.2f", lot);
   if(exitPrice > 0.0) json += StringFormat(",\"exit\":%.5f", exitPrice);
   if(pnl != 0.0)     json += StringFormat(",\"pnl_pt\":%.1f", pnl);
   json += "}\n";
   FileSeek(g_logHandle, 0, SEEK_END);
   FileWriteString(g_logHandle, json);
   FileFlush(g_logHandle);
}

//+------------------------------------------------------------------+
void LogMarketSnapshot()
{
   if(g_logHandle < 0) return;
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;
   double spreadPts = (tk.ask - tk.bid) / _Point;
   string json = StringFormat(
      "{\"t\":%d,\"action\":\"market\",\"bid\":%.5f,\"ask\":%.5f,\"spread_pts\":%.1f}\n",
      (int)TimeCurrent(), tk.bid, tk.ask, spreadPts);
   FileSeek(g_logHandle, 0, SEEK_END);
   FileWriteString(g_logHandle, json);
   FileFlush(g_logHandle);
}

//+------------------------------------------------------------------+
void OpenPatternTrade(int pi)
{
   Pattern p = g_patterns[pi];
   int cross = CachedCross(MAPeriodToBuf(p.entry));
   if(cross == 0)
   {
      if(InpLog)
         Print("   DEBUG EntryCheck: P", pi, " MA", p.entry, " cross=0 (nessun segnale)");
      return;
   }

   int wantDir = -1;
   if(p.dir == 1 && cross == +1) { wantDir = 1; if(InpLog) Print("   DEBUG EntryCheck: P", pi, " MA", p.entry, " cross=+1 -> BUY"); }
   else if(p.dir == 2 && cross == -1) { wantDir = -1; if(InpLog) Print("   DEBUG EntryCheck: P", pi, " MA", p.entry, " cross=-1 -> SELL"); }
   else { if(InpLog) Print("   DEBUG EntryCheck: P", pi, " cross=", cross, " dir=", p.dir, " -> no match"); return; }

   // Limite posizioni per pattern
   if(InpMaxPerPattern > 0)
   {
      int cnt = 0;
      for(int i = 0; i < PositionsTotal(); i++)
      {
         if(!g_pos.SelectByIndex(i)) continue;
         if(g_pos.Symbol() != _Symbol) continue;
         if(g_pos.Magic() != InpMagic) continue;
         if(GetPatternIndex(g_pos.Ticket()) == pi) cnt++;
      }
      if(cnt >= InpMaxPerPattern)
      {
         if(InpLog) Print("   Pattern ", pi, " ha gia' ", cnt, " posizioni (max ", InpMaxPerPattern, ") - salto");
         LogDecision("skip", pi, DirStr(p.dir), "Limite per-pattern raggiunto");
         return;
      }
   }

   // Spread check
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;
   double spreadPts = (tk.ask - tk.bid) / _Point;
   if(InpMaxSpread > 0 && spreadPts > InpMaxSpread) { if(InpLog) Print("   Spread troppo alto (", DoubleToString(spreadPts,0), "pt > ", InpMaxSpread, ") - salto"); LogDecision("skip", pi, DirStr(p.dir), "Spread troppo alto"); return; }

   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double entry  = (wantDir == 1) ? tk.ask : tk.bid;

   double sl = 0.0, tp = 0.0;
   double riskDist = 0.0;

   // TP fisso
   if(p.tpPt > 0)
      tp = (wantDir == 1) ? entry + p.tpPt * pt : entry - p.tpPt * pt;

   // Hard SL broker-side
   bool slValid = false;
   if(p.slLine > 0)
   {
      double slVal = 0.0;
      if(ReadBufD1(MAPeriodToBuf(p.slLine), 1, slVal) && IsPriceOk(slVal))
      {
         if(wantDir == 1 && slVal < entry) { sl = slVal; slValid = true; }
         else if(wantDir == -1 && slVal > entry) { sl = slVal; slValid = true; }
      }
      if(!slValid)
      {
         if(InpLog) Print("   Pattern ", pi, " SKIPPED: SL line ", MAPeriodStr(p.slLine),
            " non piazzabile (lato sbagliato o lettura fallita)");
         LogDecision("skip", pi, DirStr(p.dir), "SL non piazzabile: " + MAPeriodStr(p.slLine) + " lato sbagliato");
         return;
      }
      riskDist = MathAbs(entry - sl);
   }

   // Fallback sizing quando non c'e' SL configurato
   if(riskDist <= 0.0)
   {
      if(p.tpPt > 0)
         riskDist = p.tpPt * pt;
      else
         riskDist = InpFallbackRiskPips * pipSize;
   }

   // Protezione: distanza minima 50pt per evitare lotti enormi
   double minDist = InpMinSLDistPts * pt;
   if(riskDist < minDist)
   {
      if(InpLog) Print("   Pattern ", pi, " SKIPPED: riskDist troppo piccolo (",
         DoubleToString(riskDist/pt, 1), "pt < ", InpMinSLDistPts, "pt)");
      LogDecision("skip", pi, DirStr(p.dir), "riskDist troppo piccolo");
      return;
   }

   double lot = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   string cmt = "P" + IntegerToString(pi);

   if(InpLog)
      Print(StringFormat(">>> APERTURA [%d] %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f %s",
          pi, (wantDir==1?"BUY":"SELL"), lot, entry, sl, tp, cmt));
   if(g_trade.PositionOpen(_Symbol, (wantDir==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                            lot, entry, sl, tp, cmt))
      LogDecision("open", pi, (wantDir==1?"BUY":"SELL"), "", entry, sl, tp, lot);
   else if(InpLog)
      Print(">>> ERR entrata [", pi, "] retcode=", g_trade.ResultRetcode());
}

//+------------------------------------------------------------------+
void CheckPatternExits()
{
   MqlTick tk;
   SymbolInfoTick(_Symbol, tk);

   int tradeCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol) continue;
      if(g_pos.Magic() != InpMagic) continue;

      ulong ticket = g_pos.Ticket();
      int pi = GetPatternIndex(ticket);
      if(pi < 0 || pi >= g_numPatterns) continue;

      Pattern p = g_patterns[pi];
      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      bool shouldClose = false;
      string reason = "";

      if(p.exit > 0)
      {
         int exitCross = CachedCross(MAPeriodToBuf(p.exit));
         int needExit = (posType == POSITION_TYPE_BUY) ? -1 : +1;
         if(InpLog && exitCross != 0)
            Print("   DEBUG ExitCheck: P", pi, " ", (posType==POSITION_TYPE_BUY?"BUY":"SELL"),
               " exit=MA", p.exit, " cross=", exitCross, " need=", needExit,
               (exitCross==needExit?" -> CLOSE":" -> NO"));
         if(exitCross == needExit) { shouldClose = true; reason = "EXIT " + MAPeriodStr(p.exit) + " cross"; }
      }

      // SL gestito da UpdateDynamicSL() (trailing dinamico sulla linea, broker-side)
      if(InpLog && !shouldClose && p.exit <= 0)
         Print("   DEBUG NoExit: P", pi, " nessun cross-exit (uscita su SL dinamico/TP broker-side)");

      if(shouldClose)
      {
         tradeCount++;
         double entryPr = g_pos.PriceOpen();
         ENUM_POSITION_TYPE ptype = g_pos.PositionType();
         double exitPr = (ptype == POSITION_TYPE_BUY) ? tk.bid : tk.ask;
         double pnlPt = (ptype == POSITION_TYPE_BUY) ?
            (exitPr - entryPr) / _Point : (entryPr - exitPr) / _Point;
         string dirStr = (ptype == POSITION_TYPE_BUY) ? "BUY" : "SELL";

         if(g_trade.PositionClose(ticket))
         {
            LogDecision("close", pi, dirStr, reason, entryPr, 0, 0, 0, exitPr, pnlPt);
            if(InpLog) Print(">>> CHIUSO [", pi, "] ", reason, " pnl=", DoubleToString(pnlPt,1), "pt #", ticket);
         }
         else if(InpLog)
            Print(">>> ERR chiusura [", pi, "] retcode=", g_trade.ResultRetcode());
      }
   }
   if(InpLog && tradeCount > 0)
      Print("   Chiuse ", tradeCount, " posizioni questo segnale");
}

//+------------------------------------------------------------------+
// SL dinamico - replica l'analisi (pattern_mining.simulate_trade):
// ad ogni barra D1 lo stop e' il valore corrente della linea MA.
// Trascina lo stop broker-side sul valore della linea (entrambe le
// direzioni). Se la linea raggiunge il prezzo, chiude a mercato.
// Usa shift 1 (D1 chiusa): nessun look-ahead, 1 barra piu' prudente
// dell'analisi che usa il valore della barra corrente.
//+------------------------------------------------------------------+
void UpdateDynamicSL()
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   long   stopsLevel  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minStopDist = (double)stopsLevel * _Point;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i)) continue;
      if(g_pos.Symbol() != _Symbol) continue;
      if(g_pos.Magic() != InpMagic) continue;

      ulong ticket = g_pos.Ticket();
      int pi = GetPatternIndex(ticket);
      if(pi < 0 || pi >= g_numPatterns) continue;

      Pattern p = g_patterns[pi];
      if(p.slLine <= 0) continue;

      double lineVal = 0.0;
      if(!ReadBufD1(MAPeriodToBuf(p.slLine), 1, lineVal) || !IsPriceOk(lineVal))
         continue;

      ENUM_POSITION_TYPE posType = g_pos.PositionType();
      bool   buy     = (posType == POSITION_TYPE_BUY);
      double curSL   = g_pos.StopLoss();
      double curTP   = g_pos.TakeProfit();
      double entryPr = g_pos.PriceOpen();
      string dirStr  = buy ? "BUY" : "SELL";

      // La linea ha raggiunto/superato il prezzo (entro lo stops level): esci a mercato
      bool lineReached = buy ? (lineVal >= tk.bid - minStopDist)
                             : (lineVal <= tk.ask + minStopDist);
      if(lineReached)
      {
         double exitPr = buy ? tk.bid : tk.ask;
         double pnlPt  = buy ? (exitPr - entryPr) / _Point : (entryPr - exitPr) / _Point;
         if(g_trade.PositionClose(ticket))
         {
            LogDecision("close", pi, dirStr, "SL dinamico " + MAPeriodStr(p.slLine) + " toccato",
                        entryPr, 0, 0, 0, exitPr, pnlPt);
            if(InpLog) Print(">>> CHIUSO [", pi, "] SL dinamico ", MAPeriodStr(p.slLine),
                             " pnl=", DoubleToString(pnlPt,1), "pt #", ticket);
         }
         else if(InpLog)
            Print(">>> ERR chiusura SL dinamico [", pi, "] retcode=", g_trade.ResultRetcode());
         continue;
      }

      // Trascina lo stop sul valore corrente della linea (segue la MA)
      if(MathAbs(lineVal - curSL) > _Point)
      {
         if(g_trade.PositionModify(ticket, lineVal, curTP))
         {
            if(InpLog) Print("   SL trail [", pi, "] -> ", DoubleToString(lineVal, _Digits),
                             " (", MAPeriodStr(p.slLine), ")");
         }
         else if(InpLog)
            Print("   ERR SL trail [", pi, "] retcode=", g_trade.ResultRetcode());
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
   g_lastMarketLog = 0;

   InitPatterns();
   SavePosSnapshot();

   // Log decisioni su file
   g_logHandle = -1;
   if(StringLen(InpLogFile) > 0)
   {
      g_logHandle = FileOpen(InpLogFile,
         FILE_WRITE|FILE_READ|FILE_TXT|FILE_COMMON|
         FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(g_logHandle == INVALID_HANDLE)
         Print("WARNING: log file non aperto: ", InpLogFile);
      else
         Print("Log decisioni: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH), "\\Files\\", InpLogFile);
   }

   // Timer market snapshot
   if(InpMarketInterval > 0)
   {
      if(EventSetTimer(InpMarketInterval))
      {
         if(InpLog) Print("Timer market snapshot avviato: ", InpMarketInterval, "s");
      }
      else
         Print("WARNING: EventSetTimer fallito per ", InpMarketInterval, "s");
   }

   if(InpMaxLot > 0.0)
   {
      double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
      if(InpMaxLot < minLot)
      {
         Print("WARNING: InpMaxLot=", InpMaxLot, " < SYMBOL_VOLUME_MIN=", minLot, " - ignorato");
      }
   }

   if(InpLog)
      Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% maxLot=%.2f maxSpread=%d minSL=%dpt maxPos=%d maxPerPatt=%d patterns=%d",
         _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
         InpMagic, InpRiskPct, InpMaxLot, InpMaxSpread, InpMinSLDistPts, InpMaxPos, InpMaxPerPattern, g_numPatterns));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   if(g_indD1 != INVALID_HANDLE) IndicatorRelease(g_indD1);
   if(g_logHandle >= 0) FileClose(g_logHandle);
   EventKillTimer();
   if(InpLog) Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
void OnTimer()
{
   if(g_logHandle < 0) return;
   datetime now = TimeCurrent();
   if(now - g_lastMarketLog < 60) return;  // non piu' spesso di 60s
   g_lastMarketLog = now;
   LogMarketSnapshot();
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
   LogMarketSnapshot();
   LogBrokerCloses();

   if(InpLog)
      Print(StringFormat("=== SEGNALE === barra=%s D1=%s pos=%d patterns=%d equity=%.0f",
          TimeToString(g_bar0), TimeToString(d1today), PositionsTotal(), g_numPatterns, g_acc.Equity()));

   CheckPatternExits();
   UpdateDynamicSL();   // trailing SL dinamico sulla linea (allineato all'analisi)

   if(InpMaxPos > 0 && PositionsTotal() >= InpMaxPos)
   {
      if(InpLog) Print("   Max posizioni raggiunto (", InpMaxPos, ") - nessuna nuova entrata");
      SavePosSnapshot();
      return;
   }

   for(int pi = 0; pi < g_numPatterns; pi++)
      OpenPatternTrade(pi);

   SavePosSnapshot();
}
//+------------------------------------------------------------------+
