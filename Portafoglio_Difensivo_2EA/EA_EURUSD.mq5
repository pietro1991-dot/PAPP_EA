//+------------------------------------------------------------------+
//|                                                     EA_Pattern.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PHAI v2"
#property version   "2.09"
#property description "Multi-Pattern EA - Fino a 10 pattern configurabili da input"
#property description "Ogni pattern: Entry, Exit, SL, TP, Direction. Tutti in simultanea."
#property description "Linee: 0=Median, 3,7,14,30,121,182,365. Dir: 0=OFF, 1=BUY, 2=SELL"
#property description "Pattern default da ANALISI 3: entry cross + SL dinamico sulla linea + TP fisso"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <phai_push.mqh>          // libreria condivisa (mettila in MQL5/Include)

input group "======  GENERALE / RISCHIO  ======"
input string  InpIndicatorName = "PHAI_Median.ex5";

input double  InpRiskPct       = 12.0;           // Rischio % per trade
input double  InpQuotaConto     = 48.0;           // PORTAFOGLIO Difensivo 2-EA: quota conto di questo EA (%). Preimpostato a 48 (risk-parity).
input double  InpLotFixed      = 0.0;           // Lotto fisso (0=usa % rischio)
input double  InpMaxLot        = 5.0;           // Lotto massimo assoluto - tetto di sicurezza (0=usa broker)
input int     InpMaxSpreadPips = 0;            // Spread massimo in PIP (0=disabilita)
input int     InpMinSLDistPips = 5;            // Distanza SL minima in PIP
input double  InpFallbackRiskPips = 500.0;      // Risk distance in pips quando il pattern non ha SL (sizing). 500 = rischio realistico trend senza stop -> lotto piccolo. 0 = disattiva i pattern senza SL
input bool    InpDynamicSL     = true;          // true=SL trascina sulla linea MA ogni D1; false=SL statico all'entry
input int     InpMaxPos        = 0;            // Max posizioni totali (0=illimitato)
input int     InpMaxPerPattern = 0;             // Max posizioni per pattern (0=illimitato)
input int     InpMagic         = 20260623;
input string  InpLogFile       = "papp_ea_log.jsonl"; // File log decisioni (vuoto=disabilita)
input int     InpMarketInterval = 300;           // Intervallo market snapshot secondi (0=disabilita)
input bool    InpLog           = true;

input group "======  PHAI SERVER (licenza + telemetria)  ======"
input bool    InpUseServer  = false;                  // Attiva licenza + invio dati al server PHAI
input string  InpLicenseKey = "";                     // License key PHAI (dal tuo account)
input string  InpServerUrl  = "https://app.phai.io";  // URL server PHAI (autorizzalo in Strumenti>Opzioni>EA)

// TUTTI i pattern validati out-of-sample (train <=2020, test >2020).
// Due famiglie affiancate:
//  - P1-P6: ANALISI 3 (SL su linea + TP fisso) - win ~60%, drawdown contenuto.
//  - P7-P10: ANALISI 2 (uscita su incrocio MA121) - trend-following, profitto OOS
//            molto alto ma drawdown grande, niente hard SL (gap risk).
// Linee: 0=Med,3,7,14,30,121,182,365. Dir: 0=OFF, 1=BUY, 2=SELL.

input group "==  PATTERN 1 - MA30 SELL, SL=MA365, TP=15pip  =="
input bool    InpP1_On         = true;          // ATTIVA pattern 1
input int     InpP1_Entry      = 30;            // Entry line (0=Med,3,7,14,30,121,182,365)
input int     InpP1_Exit       = 0;             // Exit cross line (0=nessuno)
input int     InpP1_SL         = 365;           // SL line (0=nessuno)
input int     InpP1_TP         = 15;            // TP in PIP (0=nessuno)
input int     InpP1_Dir        = 2;             // 0=OFF, 1=BUY, 2=SELL

input group "==  PATTERN 2 - MA121 BUY, SL=MA365, TP=15pip  =="
input bool    InpP2_On         = true;          // ATTIVA pattern 2
input int     InpP2_Entry      = 121;
input int     InpP2_Exit       = 0;
input int     InpP2_SL         = 365;
input int     InpP2_TP         = 15;            // TP in PIP
input int     InpP2_Dir        = 1;

input group "==  PATTERN 3 - MA365 SELL, SL=MA121, TP=12pip  =="
input bool    InpP3_On         = true;          // ATTIVA pattern 3
input int     InpP3_Entry      = 365;
input int     InpP3_Exit       = 0;
input int     InpP3_SL         = 121;
input int     InpP3_TP         = 12;            // TP in PIP
input int     InpP3_Dir        = 2;

input group "==  PATTERN 4 - MA7 SELL, SL=MA365, TP=12pip  =="
input bool    InpP4_On         = true;          // ATTIVA pattern 4
input int     InpP4_Entry      = 7;
input int     InpP4_Exit       = 0;
input int     InpP4_SL         = 365;
input int     InpP4_TP         = 12;            // TP in PIP
input int     InpP4_Dir        = 2;

input group "==  PATTERN 5 - MA30 BUY, SL=MA365, TP=15pip  =="
input bool    InpP5_On         = true;          // ATTIVA pattern 5
input int     InpP5_Entry      = 30;
input int     InpP5_Exit       = 0;
input int     InpP5_SL         = 365;
input int     InpP5_TP         = 15;            // TP in PIP
input int     InpP5_Dir        = 1;

input group "==  PATTERN 6 - MA14 BUY, SL=MA365, TP=15pip  =="
input bool    InpP6_On         = true;          // ATTIVA pattern 6
input int     InpP6_Entry      = 14;
input int     InpP6_Exit       = 0;
input int     InpP6_SL         = 365;
input int     InpP6_TP         = 15;            // TP in PIP
input int     InpP6_Dir        = 1;

// P7-P10: TP ampio (default 150pip) come TETTO oltre all'uscita su incrocio MA121.
// Chiude su MA121 cross OPPURE al TP, quel che viene prima. TP=150pip = compromesso
// (OOS ~+192k, win 64%); modificabile da input. Metti TP=0 per il trend-following puro.

input group "==  PATTERN 7 - MA3 SELL -> cross MA121, TP cap 150pip  =="
input bool    InpP7_On         = false;          // ATTIVA pattern 7
input int     InpP7_Entry      = 3;
input int     InpP7_Exit       = 121;
input int     InpP7_SL         = 0;
input int     InpP7_TP         = 150;            // TP in PIP
input int     InpP7_Dir        = 2;

input group "==  PATTERN 8 - MA7 SELL -> cross MA121, TP cap 150pip  =="
input bool    InpP8_On         = false;          // ATTIVA pattern 8
input int     InpP8_Entry      = 7;
input int     InpP8_Exit       = 121;
input int     InpP8_SL         = 0;
input int     InpP8_TP         = 150;            // TP in PIP
input int     InpP8_Dir        = 2;

input group "==  PATTERN 9 - MA14 SELL -> cross MA121, TP cap 150pip  =="
input bool    InpP9_On         = false;          // ATTIVA pattern 9
input int     InpP9_Entry      = 14;
input int     InpP9_Exit       = 121;
input int     InpP9_SL         = 0;
input int     InpP9_TP         = 150;            // TP in PIP
input int     InpP9_Dir        = 2;

input group "==  PATTERN 10 - MA30 SELL -> cross MA121, TP cap 150pip  =="
input bool    InpP10_On        = false;          // ATTIVA pattern 10
input int     InpP10_Entry     = 30;
input int     InpP10_Exit      = 121;
input int     InpP10_SL        = 0;
input int     InpP10_TP        = 150;            // TP in PIP
input int     InpP10_Dir       = 2;

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7
#define BUF_CLUSTER 8
#define BUF_VEL     9
#define BUF_ACC     10
#define BUF_VOL     11

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
bool     g_licensed     = true;   // se server OFF, opera con gli input locali
datetime g_lastValidate = 0;
datetime g_lastOkValidate = 0;    // ultimo contatto col server con licenza valida (per la grazia)
#define  LICENSE_GRACE_SEC 604800 // grazia se il server e' irraggiungibile: 7 giorni, poi pausa

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
         if(tpHit) reason = "R|tp";
      }
      if(reason == "" && p.sl > 0.0)
      {
         bool slHit = (p.type == (int)POSITION_TYPE_BUY && tk.bid <= p.sl) ||
                      (p.type == (int)POSITION_TYPE_SELL && tk.ask >= p.sl);
         if(slHit) reason = "R|sl";
      }
      if(reason == "") reason = "R|stopout";

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

// Descrizione leggibile del setup di un pattern: ingresso + piano d'uscita.
// Registrata come "reason" all'apertura, cosi' ogni ordine dice perche' e' nato e come uscira'.
string PatternSetupStr(int pi)
{
   Pattern p = g_patterns[pi];
   // Codice neutro (tradotto dalla UI): e=entry, d=dir(1/2), x=exit, sl=linea SL, tp=pip
   string s = "SETUP|e:" + IntegerToString(p.entry) + "|d:" + IntegerToString(p.dir);
   if(p.exit > 0)   s += "|x:" + IntegerToString(p.exit);
   if(p.slLine > 0) s += "|sl:" + IntegerToString(p.slLine);
   if(p.tpPt > 0)   s += "|tp:" + IntegerToString(p.tpPt);
   return s;
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
   bool on[10] = {InpP1_On, InpP2_On, InpP3_On, InpP4_On, InpP5_On,
                  InpP6_On, InpP7_On, InpP8_On, InpP9_On, InpP10_On};

   for(int i=0; i<10; i++)
   {
      if(!on[i]) continue;          // pattern disattivato dall'interruttore
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
      Print("ATTENZIONE: Nessun pattern attivo! Attiva InpPx_On per almeno un pattern.");

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
// Lettura RAW di un buffer di calcolo D1 (cluster/vel/acc/vol): niente IsPriceOk
// perche' questi valori possono essere ~0 o negativi. Solo barra corrente (shift 0).
bool ReadCalcD1(int buf, double &val)
{
   double tmp[1];
   if(g_indD1 != INVALID_HANDLE && CopyBuffer(g_indD1, buf, 0, 1, tmp) == 1){ val = tmp[0]; return true; }
   if(CopyBuffer(g_ind, buf, 0, 1, tmp) == 1){ val = tmp[0]; return true; }
   return false;
}

//+------------------------------------------------------------------+
// Push FEATURE di mercato (Volatilità/Cluster/… + distanze dalle medie) lette da
// PHAI_Median. Scrive nel log locale (ponte) e via HTTP. t = barra D1 corrente ->
// il backend fa upsert (aggiorna ai valori freschi della giornata).
void LogFeatures()
{
   if(g_logHandle < 0) return;
   double close = iClose(_Symbol, PERIOD_D1, 0);
   if(close <= 0) return;
   double median=0, ma30=0, ma365=0, clu=0, vel=0, acc=0, vol=0;
   ReadBufD1(BUF_MEDIAN, 0, median);
   ReadBufD1(BUF_MA30,   0, ma30);
   ReadBufD1(BUF_MA365,  0, ma365);
   ReadCalcD1(BUF_CLUSTER, clu); ReadCalcD1(BUF_VEL, vel);
   ReadCalcD1(BUF_ACC,     acc); ReadCalcD1(BUF_VOL, vol);
   // OrderScore: ordine dello stack di MA (somma dei confronti a coppie, -6..+6), come Export_PAPP
   double v3=0,v7=0,v14=0,v121=0,v182=0;
   ReadBufD1(BUF_MA3,0,v3);    ReadBufD1(BUF_MA7,0,v7);    ReadBufD1(BUF_MA14,0,v14);
   ReadBufD1(BUF_MA121,0,v121);ReadBufD1(BUF_MA182,0,v182);
   double os=0;
   if(v3>0&&v7>0)      os+=(v3>v7)?1:-1;
   if(v7>0&&v14>0)     os+=(v7>v14)?1:-1;
   if(v14>0&&ma30>0)   os+=(v14>ma30)?1:-1;
   if(ma30>0&&v121>0)  os+=(ma30>v121)?1:-1;
   if(v121>0&&v182>0)  os+=(v121>v182)?1:-1;
   if(v182>0&&ma365>0) os+=(v182>ma365)?1:-1;
   double d_med  = (median > 0) ? (close-median)/median*100.0 : 0.0;
   double d_ma30 = (ma30   > 0) ? (close-ma30)/ma30*100.0     : 0.0;
   double d_ma365= (ma365  > 0) ? (close-ma365)/ma365*100.0   : 0.0;
   double spreadPt = (double)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   string json = StringFormat(
      "{\"t\":%d,\"symbol\":\"%s\",\"action\":\"features\",\"close\":%.5f,"
      "\"d_med\":%.3f,\"d_ma30\":%.3f,\"d_ma365\":%.3f,\"cluster\":%.3f,\"velocity\":%.3f,"
      "\"accel\":%.3f,\"volatility\":%.3f,\"order_score\":%.3f,\"spread\":%.3f}\n",
      (int)iTime(_Symbol, PERIOD_D1, 0), _Symbol, close, d_med, d_ma30, d_ma365,
      clu, vel, acc, vol, os, spreadPt);
   FileSeek(g_logHandle, 0, SEEK_END); FileWriteString(g_logHandle, json); FileFlush(g_logHandle);
   PhaiSend(json);
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
   double risk = g_acc.Equity() * (InpQuotaConto/100.0) * InpRiskPct / 100.0;
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
      "{\"t\":%d,\"symbol\":\"%s\",\"action\":\"%s\",\"pattern\":%d,\"dir\":\"%s\"",
      (int)TimeCurrent(), _Symbol, action, pi, dir);
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
   PhaiSend(json);
}

//+------------------------------------------------------------------+
void LogMarketSnapshot()
{
   if(g_logHandle < 0) return;
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;
   double spreadPts = (tk.ask - tk.bid) / _Point;
   string json = StringFormat(
      "{\"t\":%d,\"symbol\":\"%s\",\"action\":\"market\",\"bid\":%.5f,\"ask\":%.5f,\"spread_pts\":%.1f}\n",
      (int)TimeCurrent(), _Symbol, tk.bid, tk.ask, spreadPts);
   FileSeek(g_logHandle, 0, SEEK_END);
   FileWriteString(g_logHandle, json);
   FileFlush(g_logHandle);
   PhaiSend(json);
}

//+------------------------------------------------------------------+
// Snapshot del conto: balance/equity/margine come MetaTrader, + P/L flottante
// del simbolo corrente e profitto % (su balance). Loggato periodicamente.
void LogAccountSnapshot()
{
   if(g_logHandle < 0) return;
   double bal = g_acc.Balance();
   double symProfit = 0.0; int symOpen = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tkt = PositionGetTicket(i);
      if(tkt == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      symProfit += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
      symOpen++;
   }
   double symPct = (bal > 0.0) ? symProfit / bal * 100.0 : 0.0;
   string json = StringFormat(
      "{\"t\":%d,\"symbol\":\"%s\",\"action\":\"account\",\"balance\":%.2f,\"equity\":%.2f,"
      "\"margin\":%.2f,\"free_margin\":%.2f,\"margin_level\":%.2f,\"profit\":%.2f,"
      "\"sym_profit\":%.2f,\"sym_pct\":%.2f,\"sym_open\":%d}\n",
      (int)TimeCurrent(), _Symbol, bal, g_acc.Equity(), g_acc.Margin(), g_acc.FreeMargin(),
      g_acc.MarginLevel(), g_acc.Profit(), symProfit, symPct, symOpen);
   FileSeek(g_logHandle, 0, SEEK_END);
   FileWriteString(g_logHandle, json);
   FileFlush(g_logHandle);
   PhaiSend(json);
}

//+------------------------------------------------------------------+
// === PHAI SERVER: licenza + telemetria via WebRequest ===
// L'EA invia gli eventi (open/close/skip/account/market) e valida la licenza.
// In ingresso parla JSON; le risposte sono key=value (facili da parsare).
// === PHAI: adapter sottili verso la libreria condivisa phai_push.mqh (logica single-source) ===
// La logica vera (WebRequest, licenza+grazia+kill-switch, parsing) vive in phai_push.mqh.
// Qui restano solo wrapper col nome storico, così i punti di chiamata non cambiano.
string PhaiEsc(string s){ return PappEsc(s); }
string PhaiHttpPost(string path, string body){ return PappPost(path, body); }
string PhaiKv(string resp, string key){ return PappKv(resp, key); }
void   PhaiSend(string jsonline){ PappSendLine(jsonline); }
bool   PhaiValidate()
{
   g_lastValidate = TimeCurrent();
   g_licensed = PappValidate(_Symbol, IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)),
                             AccountInfoString(ACCOUNT_COMPANY));
   return g_licensed;
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
         LogDecision("skip", pi, DirStr(p.dir), "R|skip_perpat");
         return;
      }
   }

   double pt     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;

   // Spread check (in pip)
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;
   double spreadPips = (tk.ask - tk.bid) / pipSize;
   if(InpMaxSpreadPips > 0 && spreadPips > InpMaxSpreadPips) { if(InpLog) Print("   Spread troppo alto (", DoubleToString(spreadPips,1), "pip > ", InpMaxSpreadPips, ") - salto"); LogDecision("skip", pi, DirStr(p.dir), "R|skip_spread"); return; }

   double entry  = (wantDir == 1) ? tk.ask : tk.bid;

   double sl = 0.0, tp = 0.0;
   double riskDist = 0.0;

   // TP fisso (in pip)
   if(p.tpPt > 0)
      tp = (wantDir == 1) ? entry + p.tpPt * pipSize : entry - p.tpPt * pipSize;

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
         LogDecision("skip", pi, DirStr(p.dir), "R|skip_slunplace:" + IntegerToString(p.slLine));
         return;
      }
      riskDist = MathAbs(entry - sl);
   }

   // Fallback sizing quando non c'e' SL configurato.
   // NON usare il TP come distanza di rischio: per i pattern trend-following
   // (es. P7-10, uscita su cross MA121) un TP stretto sovradimensiona il lotto
   // fino al rifiuto del broker (retcode 10019 "not enough money"). Il rischio
   // reale e' il movimento avverso fino all'uscita, non il target di profitto.
   if(riskDist <= 0.0)
      riskDist = InpFallbackRiskPips * pipSize;

   // Protezione: distanza minima (pip) per evitare lotti enormi
   double minDist = InpMinSLDistPips * pipSize;
   if(riskDist < minDist)
   {
      if(InpLog) Print("   Pattern ", pi, " SKIPPED: riskDist troppo piccolo (",
         DoubleToString(riskDist/pipSize, 1), "pip < ", InpMinSLDistPips, "pip)");
      LogDecision("skip", pi, DirStr(p.dir), "R|skip_riskdist");
      return;
   }

   double lot = CalcLotByDist(riskDist);
   if(lot <= 0.0) return;

   string cmt = "P" + IntegerToString(pi);

   if(InpLog)
      Print(StringFormat(">>> APERTURA [%d] %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f %s",
          pi, (wantDir==1?"BUY":"SELL"), lot, entry, sl, tp, cmt));
   TrySendEntry(pi, wantDir, lot, sl, tp, cmt);
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
         if(exitCross == needExit) { shouldClose = true; reason = "R|exit:" + IntegerToString(p.exit); }
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
   if(!InpDynamicSL) return;   // SL statico: lo stop resta al valore impostato all'entry

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
            LogDecision("close", pi, dirStr, "R|sldyn:" + IntegerToString(p.slLine),
                        entryPr, 0, 0, 0, exitPr, pnlPt);
            if(InpLog) Print(">>> CHIUSO [", pi, "] SL dinamico ", MAPeriodStr(p.slLine),
                             " pnl=", DoubleToString(pnlPt,1), "pt #", ticket);
         }
         else
         {
            uint rc = g_trade.ResultRetcode();
            if(IsRetryableRetcode(rc))
               EnqueuePendingSL(ticket, true, 0, 0, pi, buy, entryPr, p.slLine);
            else if(InpLog)
               Print(">>> ERR chiusura SL dinamico [", pi, "] retcode=", rc);
         }
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
         else
         {
            uint rc = g_trade.ResultRetcode();
            if(IsRetryableRetcode(rc))
               EnqueuePendingSL(ticket, false, lineVal, curTP, pi, buy, entryPr, p.slLine);
            else if(InpLog)
               Print("   ERR SL trail [", pi, "] retcode=", rc);
         }
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
   if(StringLen(InpLogFile) > 0 && !MQLInfoInteger(MQL_TESTER))
   {
      // un file PER EA (papp_ea_<SIMBOLO>.jsonl): evita collisioni di scrittura tra EA
      string lf = (InpLogFile!="papp_ea_log.jsonl") ? InpLogFile : ("papp_ea_"+_Symbol+".jsonl");
      g_logHandle = FileOpen(lf,
         FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|
         FILE_SHARE_READ|FILE_SHARE_WRITE);
      if(g_logHandle == INVALID_HANDLE)
         Print("WARNING: log file non aperto: ", lf);
      else
         Print("PAPP ", _Symbol, " log: ", TerminalInfoString(TERMINAL_COMMONDATA_PATH), "\\Files\\", lf);
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
      Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% maxLot=%.2f maxSpread=%dpip minSL=%dpip maxPos=%d maxPerPatt=%d patterns=%d",
         _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
         InpMagic, InpRiskPct, InpMaxLot, InpMaxSpreadPips, InpMinSLDistPips, InpMaxPos, InpMaxPerPattern, g_numPatterns));

   if(InpUseServer)
   {
      if(StringLen(InpLicenseKey) == 0) Print("PHAI: InpUseServer attivo ma License key vuota.");
      PappInit(InpUseServer, InpServerUrl, InpLicenseKey);   // configura la libreria condivisa
      PhaiValidate();   // lega la key al conto e verifica l'abbonamento all'avvio
   }
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
// Export backtest: a fine test scrive UN record per trade (dalla cronologia deal
// di MT5 = verita' assoluta) in papp_backtest_<simbolo>.csv. Solo in tester.
void WriteBacktestTrades()
{
   if(!MQLInfoInteger(MQL_TESTER)) return;
   if(!HistorySelect(0, TimeCurrent())) return;
   int total = HistoryDealsTotal();

   long inPos[]; datetime inTime[]; double inPrice[]; double inVol[]; string inCmt[]; long inType[];
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_IN) continue;
      int n = ArraySize(inPos);
      ArrayResize(inPos, n+1); ArrayResize(inTime, n+1); ArrayResize(inPrice, n+1);
      ArrayResize(inVol, n+1); ArrayResize(inCmt, n+1); ArrayResize(inType, n+1);
      inPos[n]   = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      inTime[n]  = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      inPrice[n] = HistoryDealGetDouble(tk, DEAL_PRICE);
      inVol[n]   = HistoryDealGetDouble(tk, DEAL_VOLUME);
      inCmt[n]   = HistoryDealGetString(tk, DEAL_COMMENT);
      inType[n]  = HistoryDealGetInteger(tk, DEAL_TYPE);
   }

   int fh = FileOpen("papp_backtest_" + _Symbol + ".csv",
                     FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(fh == INVALID_HANDLE) { Print("Backtest export: impossibile aprire il file"); return; }
   FileWrite(fh, "symbol","pattern","dir","entry_time","entry_price","exit_time",
             "exit_price","lot","pnl_pt","pnl_money","reason","duration_d");

   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT); if(pt <= 0) pt = _Point;
   int written = 0;
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol) continue;
      if(HistoryDealGetInteger(tk, DEAL_ENTRY) != DEAL_ENTRY_OUT) continue;
      long posid = HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      int idx = -1;
      for(int k = 0; k < ArraySize(inPos); k++) if(inPos[k] == posid) { idx = k; break; }
      if(idx < 0) continue;

      string cmt = inCmt[idx];
      int pat = -1;
      if(StringLen(cmt) >= 2 && StringGetCharacter(cmt, 0) == 'P')
         pat = (int)StringToInteger(StringSubstr(cmt, 1));
      string dir = (inType[idx] == DEAL_TYPE_BUY) ? "BUY" : "SELL";

      datetime et = inTime[idx];
      double   ep = inPrice[idx];
      double   lot = inVol[idx];
      datetime xt = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);
      double   xp = HistoryDealGetDouble(tk, DEAL_PRICE);
      double   money = HistoryDealGetDouble(tk, DEAL_PROFIT)
                     + HistoryDealGetDouble(tk, DEAL_SWAP)
                     + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      double   pnlpt = ((dir == "BUY") ? (xp - ep) : (ep - xp)) / pt;
      double   durd  = (double)(xt - et) / 86400.0;
      string   reason = HistoryDealGetString(tk, DEAL_COMMENT);

      FileWrite(fh, _Symbol, pat, dir,
                TimeToString(et, TIME_DATE|TIME_MINUTES), DoubleToString(ep, 5),
                TimeToString(xt, TIME_DATE|TIME_MINUTES), DoubleToString(xp, 5),
                DoubleToString(lot, 2), DoubleToString(pnlpt, 1),
                DoubleToString(money, 2), reason, DoubleToString(durd, 1));
      written++;
   }
   FileClose(fh);
   Print("Backtest export: ", written, " trade in papp_backtest_", _Symbol, ".csv");
}

void OnDeinit(const int reason)
{
   WriteBacktestTrades();
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   if(g_indD1 != INVALID_HANDLE) IndicatorRelease(g_indD1);
   if(g_logHandle >= 0) FileClose(g_logHandle);
   EventKillTimer();
   if(InpLog) Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
void OnTimer()
{
   if(g_logHandle < 0){ Print("PAPP ", _Symbol, ": timer attivo ma log file chiuso (snapshot non inviati)."); return; }
   datetime now = TimeCurrent();
   if(now - g_lastMarketLog < 60) return;  // non piu' spesso di 60s
   g_lastMarketLog = now;
   LogMarketSnapshot();
   LogAccountSnapshot();
   LogFeatures();
   PrintFormat("PAPP %s: snapshot mercato+conto+feature inviato | equity=%.2f | bal=%.2f",
               _Symbol, AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoDouble(ACCOUNT_BALANCE));
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
//+------------------------------------------------------------------+
//  Entrate differite: se il broker rifiuta l'ordine per una causa
//  transitoria (es. 10018 "mercato chiuso" al primo tick della barra a
//  mezzanotte server, requote, off-quotes), l'entrata viene messa in
//  coda e ritentata a ogni tick finche' il mercato apre, ma solo entro
//  la stessa barra D1. Senza questo, su broker con sessione chiusa a
//  mezzanotte (es. ICMarkets) ~meta' dei segnali venivano persi e il
//  backtest risultava completamente falsato rispetto ad altri broker.
//+------------------------------------------------------------------+
#define MAX_PENDING 64
struct PendingEntry
{
   bool     active;
   int      pi;
   int      wantDir;   // +1 BUY, -1 SELL
   double   lot;
   double   sl;
   double   tp;
   string   cmt;
   datetime d1bar;
   int      attempts;
};
PendingEntry g_pending[MAX_PENDING];

bool IsRetryableRetcode(uint rc)
{
   switch(rc)
   {
      case 10004: // requote
      case 10006: // richiesta rifiutata
      case 10018: // mercato chiuso
      case 10021: // nessuna quotazione (off quotes)
      case 10024: // troppe richieste
      case 10031: // nessuna connessione
         return true;
   }
   return false;
}

void EnqueuePending(int pi, int wantDir, double lot, double sl, double tp, string cmt, datetime d1bar)
{
   for(int i = 0; i < MAX_PENDING; i++)
      if(!g_pending[i].active)
      {
         g_pending[i].active   = true;
         g_pending[i].pi       = pi;
         g_pending[i].wantDir  = wantDir;
         g_pending[i].lot      = lot;
         g_pending[i].sl       = sl;
         g_pending[i].tp       = tp;
         g_pending[i].cmt      = cmt;
         g_pending[i].d1bar    = d1bar;
         g_pending[i].attempts = 0;
         return;
      }
   if(InpLog) Print("   Coda entrate piena: P", pi, " scartata");
}

void TrySendEntry(int pi, int wantDir, double lot, double sl, double tp, string cmt)
{
   double px = (wantDir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                              : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(g_trade.PositionOpen(_Symbol, (wantDir==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                            lot, px, sl, tp, cmt))
   {
      LogDecision("open", pi, (wantDir==1?"BUY":"SELL"), PatternSetupStr(pi), px, sl, tp, lot);
      return;
   }
   uint rc = g_trade.ResultRetcode();
   if(IsRetryableRetcode(rc))
   {
      EnqueuePending(pi, wantDir, lot, sl, tp, cmt, iTime(_Symbol, PERIOD_D1, 0));
      if(InpLog) Print(">>> entrata [", pi, "] differita (retcode=", rc, "): mercato non disponibile, riprovo");
   }
   else if(InpLog)
      Print(">>> ERR entrata [", pi, "] retcode=", rc, " (non ritentabile)");
}

void RetryPending()
{
   datetime d1now = iTime(_Symbol, PERIOD_D1, 0);
   for(int i = 0; i < MAX_PENDING; i++)
   {
      if(!g_pending[i].active) continue;

      // Segnale scaduto: barra D1 cambiata -> non e' piu' valido
      if(g_pending[i].d1bar != d1now)
      {
         if(InpLog) Print("   Pending P", g_pending[i].pi, " scaduto (nuova barra) dopo ",
                          g_pending[i].attempts, " tentativi");
         g_pending[i].active = false;
         continue;
      }

      if(InpMaxPos > 0 && PositionsTotal() >= InpMaxPos) { g_pending[i].active = false; continue; }

      g_pending[i].attempts++;
      int    wd = g_pending[i].wantDir;
      double px = (wd == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                            : SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(px <= 0.0) continue;

      // L'hard SL deve restare dal lato corretto rispetto al prezzo aggiornato
      double sl = g_pending[i].sl;
      if(sl > 0.0 && ((wd == 1 && sl >= px) || (wd == -1 && sl <= px))) continue;

      if(g_trade.PositionOpen(_Symbol, (wd==1)?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                               g_pending[i].lot, px, sl, g_pending[i].tp, g_pending[i].cmt))
      {
         if(InpLog) Print(">>> entrata [", g_pending[i].pi, "] RIUSCITA al ritentativo #", g_pending[i].attempts);
         LogDecision("open", g_pending[i].pi, (wd==1?"BUY":"SELL"), PatternSetupStr(g_pending[i].pi),
                     px, sl, g_pending[i].tp, g_pending[i].lot);
         g_pending[i].active = false;
      }
      else
      {
         uint rc = g_trade.ResultRetcode();
         if(!IsRetryableRetcode(rc))
         {
            if(InpLog) Print(">>> ERR pending [", g_pending[i].pi, "] retcode=", rc, " - scartato");
            g_pending[i].active = false;
         }
      }
   }
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//  Stessa logica di retry per le operazioni sullo stop dinamico
//  (chiusura su linea raggiunta e trailing dello SL): se a mezzanotte
//  il broker rifiuta con "market closed", l'operazione viene accodata e
//  ritentata a ogni tick entro la stessa barra. La DECISIONE resta
//  congelata alla valutazione di nuova barra: nessuna uscita intraday,
//  cambia solo il momento in cui l'ordine viene effettivamente eseguito.
//+------------------------------------------------------------------+
struct PendingSL
{
   bool     active;
   ulong    ticket;
   bool     isClose;   // true = chiusura a mercato, false = modifica SL
   double   sl;
   double   tp;
   int      pi;
   bool     buy;
   double   entryPr;
   int      slLine;
   datetime d1bar;
   int      attempts;
};
PendingSL g_pendSL[MAX_PENDING];

void EnqueuePendingSL(ulong ticket, bool isClose, double sl, double tp,
                      int pi, bool buy, double entryPr, int slLine)
{
   datetime d1 = iTime(_Symbol, PERIOD_D1, 0);
   // Una sola operazione pendente per ticket: l'ultima decisione vince
   int slot = -1;
   for(int i = 0; i < MAX_PENDING; i++)
      if(g_pendSL[i].active && g_pendSL[i].ticket == ticket) { slot = i; break; }
   if(slot < 0)
      for(int i = 0; i < MAX_PENDING; i++)
         if(!g_pendSL[i].active) { slot = i; break; }
   if(slot < 0) return;
   g_pendSL[slot].active   = true;
   g_pendSL[slot].ticket   = ticket;
   g_pendSL[slot].isClose  = isClose;
   g_pendSL[slot].sl       = sl;
   g_pendSL[slot].tp       = tp;
   g_pendSL[slot].pi       = pi;
   g_pendSL[slot].buy      = buy;
   g_pendSL[slot].entryPr  = entryPr;
   g_pendSL[slot].slLine   = slLine;
   g_pendSL[slot].d1bar    = d1;
   g_pendSL[slot].attempts = 0;
}

void RetryPendingSL()
{
   datetime d1now = iTime(_Symbol, PERIOD_D1, 0);
   for(int i = 0; i < MAX_PENDING; i++)
   {
      if(!g_pendSL[i].active) continue;
      if(g_pendSL[i].d1bar != d1now)                  { g_pendSL[i].active = false; continue; } // scaduta
      if(!PositionSelectByTicket(g_pendSL[i].ticket)) { g_pendSL[i].active = false; continue; } // gia' chiusa (TP/SL)

      g_pendSL[i].attempts++;

      if(g_pendSL[i].isClose)
      {
         MqlTick tk;
         if(!SymbolInfoTick(_Symbol, tk)) continue;
         double exitPr = g_pendSL[i].buy ? tk.bid : tk.ask;
         if(g_trade.PositionClose(g_pendSL[i].ticket))
         {
            double pnlPt = g_pendSL[i].buy ? (exitPr - g_pendSL[i].entryPr) / _Point
                                           : (g_pendSL[i].entryPr - exitPr) / _Point;
            LogDecision("close", g_pendSL[i].pi, g_pendSL[i].buy?"BUY":"SELL",
                        "R|sldyn:" + IntegerToString(g_pendSL[i].slLine),
                        g_pendSL[i].entryPr, 0, 0, 0, exitPr, pnlPt);
            if(InpLog) Print(">>> CHIUSO [", g_pendSL[i].pi, "] SL dinamico al ritentativo #", g_pendSL[i].attempts);
            g_pendSL[i].active = false;
         }
         else if(!IsRetryableRetcode(g_trade.ResultRetcode())) g_pendSL[i].active = false;
      }
      else
      {
         if(g_trade.PositionModify(g_pendSL[i].ticket, g_pendSL[i].sl, g_pendSL[i].tp))
         {
            if(InpLog) Print("   SL trail [", g_pendSL[i].pi, "] eseguito al ritentativo #", g_pendSL[i].attempts);
            g_pendSL[i].active = false;
         }
         else if(!IsRetryableRetcode(g_trade.ResultRetcode())) g_pendSL[i].active = false;
      }
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!WaitIndicator()) return;
   RetryPending();
   RetryPendingSL();
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

   // Licenza/strategia dal server: re-valida ogni 6h e blocca nuove entrate se non valida.
   if(InpUseServer && TimeCurrent() - g_lastValidate > 21600) PhaiValidate();
   if(InpUseServer && !g_licensed)
   {
      if(InpLog) Print("PHAI: licenza/strategia non attiva — niente nuove entrate (le posizioni aperte restano gestite).");
      SavePosSnapshot();
      return;
   }

   for(int pi = 0; pi < g_numPatterns; pi++)
      OpenPatternTrade(pi);

   SavePosSnapshot();
}
//+------------------------------------------------------------------+
