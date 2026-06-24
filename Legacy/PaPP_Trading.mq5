//+------------------------------------------------------------------+
//|                                                   PaPP_Trading.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.10"
#property description "PaPP EA - Trend Following + Mean Reversion"
#property description "Segnale su barra chiusa (shift 1), Uscita su MA365 corrente"
#property description "1% rischiato per ordine | Cache lectio-only"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

//+------------------------------------------------------------------+
//--- INPUT
//+------------------------------------------------------------------+
input group   "==========  INDICATOR  =========="
input string  InpIndicatorName = "PaPP_Median.ex5";  // Nome file indicatore

input group   "==========  RISK  =========="
input double  InpRiskPct  = 1.0;       // % capitale rischiata per ordine
input int     InpMagic    = 20240618;   // Magic number

input group   "==========  EXIT STRATEGY  =========="
input bool    InpUseSL   = true;       // Usa Stop Loss su MA
input int     InpSL_MA   = 365;        // SL: period MA (0=Median/3/7/14/30/121/182/365)
input bool    InpUseTP   = true;       // Usa Take Profit su MA
input int     InpTP_MA   = 3;          // TP: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpFallbackTP = 50;      // TP fisso in pt se MA e' oltre entry
input bool    InpUseLongFilter = false;// Filtro MA lunghe: BUY solo sopra MA121/182/365
input bool    InpUseClusterFilter = false;// Blocca entry se prezzo dentro le MA lunghe (tra min e max)

input group   "==========  MARGIN MANAGEMENT  =========="
input bool    InpUseMargin = true;     // Gestione automatica margine
input double  InpMargTrig  = 150.0;    // Soglia crisi % (< questo attiva)
input double  InpMargTarg  = 200.0;    // Target recupero % (≥ questo stop)

input group   "==========  GROUP TREND & REVERSAL  =========="
input bool    InpUseMA30  = true;      // Metodo 1: MA7/MA14 vs MA30
input bool    InpUseOrder = false;     // Metodo 2: Ordinamento MA (ventaglio)
input bool    InpUseSpread= false;     // Metodo 3: Spread veloci vs lenti
input bool    InpRevAllLines = true;   // Reversal: servono TUTTE le brevi MA7+MA14 (false=una basta)
input bool    InpUseMedCrossExit = false;// Chiudi TUTTE se MA7/14 incrociano MA30
input bool    InpUseFlipExit = true;   // Chiudi posizioni opposte nuovo trend

input group   "==========  DEBUG  =========="
input bool    InpLog      = true;       // Stampa log nell Expert tab

//+------------------------------------------------------------------+
//--- INDICATOR BUFFERS
//+------------------------------------------------------------------+
#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

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
//--- CACHE (solo shift 1 - barra chiusa)
//+------------------------------------------------------------------+
struct Snapshot
{
   double   median, ma365, ma182, ma121, ma30, close;
   double   ma14, ma7, ma3;
   datetime bartime;
   bool     ready;
};
Snapshot g_snap;

//+------------------------------------------------------------------+
//--- GLOBALS
//+------------------------------------------------------------------+
CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

int      g_ind  = INVALID_HANDLE;         // handle iCustom
datetime g_bar0 = 0;                      // ultima barra 0 vista
bool     g_ready= false;
int      g_wait = 0;
int      g_firstBarCheck = 0;            // 0=non ancora, 1=attendo, 2=ok

// Stato L1+L2 per entry tick-by-tick
bool     g_trendBuy  = false;
bool     g_trendSell = false;
double   g_medLevel  = 0.0;
double   g_ma365SL   = 0.0;              // MA365 shift=0 per SL
bool     g_entryDone = false;            // 1 entry per barra
bool     g_marginCrisis = false;         // sotto soglia, in recupero verso target

int      g_slBuf = BUF_MA365;            // buffer SL (da input)
int      g_tpBuf = BUF_MA3;              // buffer TP (da input)

// Stato group trend / reversal
bool     g_shortAbove   = false;         // short MAs sopra mediana (barra chiusa)
int      g_prevShortAboveCnt = -1;       // conteggio barra precedente (-1 = non inizializzato)
int      g_shortAboveCnt = 0;            // conteggio corrente (0-2: MA7+MA14)
bool     g_reversal     = false;         // reversal appena avvenuto
bool     g_useGroupTrend = false;        // group alignment attivo
bool     g_groupBullish  = false;        // long sotto + short sopra mediana
bool     g_groupBearish  = false;        // long sopra + short sotto mediana
bool     g_medCrossDone = false;         // one-shot MonitorMedCross per barra
bool     g_prevTrendBuy = false;         // trend barra precedente (per auto-close)
bool     g_prevTrendSell = false;

// Metodi multipli di trend
int      g_orderScore   = 0;             // -6..+6: ordinamento ventaglio
double   g_spread       = 0.0;           // veloci - lenti
double   g_prevSpread   = 0.0;           // spread barra precedente
double   g_spreadVel    = 0.0;           // velocita' apertura frattale
int      g_voteSum      = 0;             // somma voti metodi attivi
int      g_prevVoteSum  = 0;             // voto barra precedente (0 = prima)

//+------------------------------------------------------------------+
void Log(string msg)
{
   if(InpLog)
      Print(TimeToString(TimeCurrent(), TIME_DATE|TIME_MINUTES|TIME_SECONDS),
            " | ", msg);
}

//+------------------------------------------------------------------+
bool IsPriceOk(double v)
{
   return (v > 0.0 && v < 1.0e12);
}

//+------------------------------------------------------------------+
string ErrTxt()
{
   return IntegerToString(GetLastError());
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);

   g_ind = iCustom(_Symbol, _Period, InpIndicatorName);
   if(g_ind == INVALID_HANDLE)
   {
      Print("FATAL: iCustom fallito per '", InpIndicatorName,
            "'. Copia il file in <data>/MQL5/Indicators/");
      return INIT_FAILED;
   }

   g_snap.ready   = false;
   g_snap.bartime = 0;
   g_bar0         = 0;
   g_ready        = false;
   g_wait         = 0;
   g_firstBarCheck = 0;
   g_marginCrisis   = false;
    g_shortAbove       = false;
    g_shortAboveCnt    = 0;
    g_prevShortAboveCnt = -1;
    g_reversal       = false;
    g_useGroupTrend  = false;
    g_groupBullish   = false;
    g_groupBearish   = false;
    g_medCrossDone    = false;
    g_prevTrendBuy    = false;
    g_prevTrendSell   = false;
    g_orderScore      = 0;
    g_spread          = 0.0;
    g_voteSum         = 0;
    g_prevVoteSum     = 0;
    g_slBuf = MAPeriodToBuf(InpSL_MA);
   g_tpBuf = MAPeriodToBuf(InpTP_MA);

    Log(StringFormat("INIT OK | sym=%s tf=%s ind=%s magic=%d risk=%.1f%% "
        "SL=%s TP=%s FB=%dpt Mgmt=%d LongFlt=%d ClusFlt=%d "
        "MA30=%d Order=%d Spread=%d RevAll=%d MedX=%d Flip=%d",
       _Symbol,
       EnumToString((ENUM_TIMEFRAMES)_Period),
       InpIndicatorName,
       InpMagic,
        InpRiskPct,
        MAPeriodStr(InpSL_MA), MAPeriodStr(InpTP_MA), InpFallbackTP, InpUseMargin,
        InpUseLongFilter,
        InpUseClusterFilter,
        InpUseMA30, InpUseOrder, InpUseSpread,
        InpRevAllLines, InpUseMedCrossExit, InpUseFlipExit));

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE)
      IndicatorRelease(g_ind);
   Log("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
//--- ATTESA INIZIALIZZAZIONE INDICATORE
//+------------------------------------------------------------------+
bool WaitIndicator()
{
   if(g_ready) return true;

   double tmp[1];
   int got = CopyBuffer(g_ind, BUF_MEDIAN, 1, 1, tmp);
   if(got == 1 && IsPriceOk(tmp[0]))
   {
      g_ready = true;
      Log(StringFormat("Indicatore PRONTO: mediana=%.5f (wait=%d)", tmp[0], g_wait));
      return true;
   }

   g_wait++;
   if(g_wait <= 3 || (g_wait % 200) == 0)
      Log(StringFormat("In attesa indicatore... got=%d wait=%d", got, g_wait));
   return false;
}

//+------------------------------------------------------------------+
//--- LETTURA SINGOLO BUFFER INDICATORE A SHIFT FISSATO
//+------------------------------------------------------------------+
bool ReadBuf(int buf, int shift, double &out)
{
   if(g_ind == INVALID_HANDLE)
   {
      Log("ReadBuf: handle invalido");
      return false;
   }

   double tmp[1];
   int got = CopyBuffer(g_ind, buf, shift, 1, tmp);
   if(got != 1)
   {
      Log(StringFormat("ReadBuf ERR: buf=%d shift=%d got=%d err=%s",
          buf, shift, got, ErrTxt()));
      return false;
   }

   out = tmp[0];
   if(!IsPriceOk(out))
   {
      Log(StringFormat("ReadBuf: buf=%d shift=%d valore=%g non valido",
          buf, shift, out));
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//--- RICARICA CACHE + LIVELLO 1 (a barra chiusa, shift=1)
//+------------------------------------------------------------------+
bool RefreshSnapshot()
{
   datetime bt = iTime(_Symbol, _Period, 1);
   if(bt == 0)
   {
      Log("RefreshSnapshot: iTime(1)=0 (poche barre sul grafico)");
      return false;
   }

   if(g_snap.ready && g_snap.bartime == bt)
      return true;

   double med, m365, m182, m121, m30, m14, m7, m3, cls;
   if(!ReadBuf(BUF_MEDIAN, 1, med))  return false;
   if(!ReadBuf(BUF_MA365,  1, m365)) return false;
   if(!ReadBuf(BUF_MA182,  1, m182)) return false;
   if(!ReadBuf(BUF_MA121,  1, m121)) return false;
   if(!ReadBuf(BUF_MA30,   1, m30))  return false;
   if(!ReadBuf(BUF_MA14,   1, m14))  return false;
   if(!ReadBuf(BUF_MA7,    1, m7))   return false;
   if(!ReadBuf(BUF_MA3,    1, m3))   return false;

   cls = iClose(_Symbol, _Period, 1);
   if(!IsPriceOk(cls))
   {
      Log("RefreshSnapshot: close(1)=" + DoubleToString(cls, _Digits));
      return false;
   }

   g_snap.median  = med;
   g_snap.ma365   = m365;
   g_snap.ma182   = m182;
   g_snap.ma121   = m121;
   g_snap.ma30    = m30;
   g_snap.ma14    = m14;
   g_snap.ma7     = m7;
   g_snap.ma3     = m3;
   g_snap.close   = cls;
   g_snap.bartime = bt;
   g_snap.ready   = true;
   g_medLevel     = med;

    // --- Short MAs vs MA30 (Metodo 1) ---
    bool s14 = (m14 > m30), s7 = (m7 > m30);
    g_shortAboveCnt = (s14?1:0) + (s7?1:0);

    // --- Salva per la prossima barra (DOPO il calcolo) ---
    g_prevShortAboveCnt = g_shortAboveCnt;

    if(InpRevAllLines)
       g_shortAbove = (g_shortAboveCnt == 2);         // MA7+MA14 tutte sopra
    else
       g_shortAbove = (g_shortAboveCnt >= 1);         // almeno una sopra

    // --- Ordinamento ventaglio (Metodo 2) ---
    // Confronto 6 coppie adiacenti: MA3>MA7, MA7>MA14, ..., MA182>MA365
    g_orderScore = 0;
    if(m3 > m7)  g_orderScore++; else g_orderScore--;
    if(m7 > m14) g_orderScore++; else g_orderScore--;
    if(m14 > m30) g_orderScore++; else g_orderScore--;
    if(m30 > m121) g_orderScore++; else g_orderScore--;
    if(m121 > m182) g_orderScore++; else g_orderScore--;
    if(m182 > m365) g_orderScore++; else g_orderScore--;

    // --- Spread Frattale: veloci vs lenti (Metodo 3, esclusa MA30) ---
    double fastAvg = (m3 + m7 + m14) / 3.0;          // Squadra Veloce: 3gg, 1sett, 2sett
    double slowAvg = (m121 + m182 + m365) / 3.0;      // Squadra Lenta: 4mesi, 6mesi, 1anno
    g_spread = fastAvg - slowAvg;
    g_spreadVel = g_spread - g_prevSpread;                // Velocita' apertura
    g_prevSpread = g_spread;

    // --- Voto: ogni metodo attivo vota +1 (BUY) o -1 (SELL) ---
    g_voteSum = 0;
    if(InpUseMA30)  g_voteSum += (g_shortAbove ? 1 : -1);
    if(InpUseOrder) g_voteSum += (g_orderScore > 0 ? 1 : (g_orderScore < 0 ? -1 : 0));
    if(InpUseSpread) g_voteSum += (g_spread > 0 ? 1 : (g_spread < 0 ? -1 : 0));

    // --- Reversal: cambio segno del voto ---
    g_reversal = (g_prevVoteSum != 0 && (g_prevVoteSum > 0) != (g_voteSum > 0));
    g_prevVoteSum = g_voteSum;

    // --- Trend dal voto ---
    g_trendBuy  = (g_voteSum > 0);
    g_trendSell = (g_voteSum < 0);

    // --- Group alignment (long vs mediana) ---
    bool longAbove = (m365 > med && m182 > med && m121 > med);
    bool longBelow = (m365 < med && m182 < med && m121 < med);
    g_groupBullish  = (longBelow && g_trendBuy);
    g_groupBearish  = (longAbove && g_trendSell);
    g_useGroupTrend = (g_groupBearish || g_groupBullish);

    // --- LOG ---
    string sDir = g_shortAbove ? "SOPRA" : "SOTTO";
    string gDir = "";
    if(g_useGroupTrend)  gDir = g_groupBullish ? " BULL-group" : " BEAR-group";
    else if(g_reversal)  gDir = g_trendBuy ? " REV-BUY" : " REV-SELL";
    else                 gDir = g_trendBuy ? " TREND-BUY" : " TREND-SELL";

    Log(StringFormat("SNAP bar=%s cls=%.5f med=%.5f | "
        "MA30=%.5f S14=%.5f S7=%.5f S3=%.5f MA3%smed | "
        "ord=%+d spread=%+.6f vel=%+.6f vote=%+d | %s rev=%d",
        TimeToString(bt), cls, med,
        m30, m14, m7, m3, (m3 > med) ? ">" : "<",
        g_orderScore, g_spread, g_spreadVel, g_voteSum,
        sDir + gDir, g_reversal));

   if(!g_trendBuy && !g_trendSell)
      Log("TREND: nessun trend attivo - nessun entry possibile");

   return true;
}

//+------------------------------------------------------------------+
//--- TICK-BY-TICK: LIVELLO 2 (incrocio mediana) + ENTRY
//+------------------------------------------------------------------+
void CheckEntry()
{
   if(g_entryDone) return;                // 1 entry per barra
   if(!g_snap.ready) return;
   if(!g_trendBuy && !g_trendSell) return;

   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   bool closePast = (g_trendBuy && g_snap.close < g_medLevel) ||
                     (g_trendSell && g_snap.close > g_medLevel);
   bool tickPast  = (g_trendBuy && tk.bid < g_medLevel) ||
                     (g_trendSell && tk.ask > g_medLevel);

   if(!closePast && !tickPast) return;

   // Filtro cluster: blocca se prezzo dentro la fascia delle MA lunghe (qualsiasi ordine)
   if(InpUseClusterFilter)
   {
      double lo = MathMin(g_snap.ma121, MathMin(g_snap.ma182, g_snap.ma365));
      double hi = MathMax(g_snap.ma121, MathMax(g_snap.ma182, g_snap.ma365));
      bool inside = (g_snap.close > lo && g_snap.close < hi);
      if(inside)
      {
         Log(StringFormat("CLUSTER FILTER: close=%.5f DENTRO [%.5f .. %.5f] - entry bloccata", g_snap.close, lo, hi));
         return;
      }
      Log(StringFormat("CLUSTER FILTER: close=%.5f FUORI [%.5f .. %.5f] - via libera", g_snap.close, lo, hi));
   }

   // Se entri per closePast, verifica distanza SL sufficiente
   // (evita lotti enormi quando prezzo e' vicino a MA365 all'apertura)
   if(closePast)
   {
      double slPrice = g_ma365SL;
      double entry   = (g_trendBuy) ? tk.bid : tk.ask;
      double slDist  = MathAbs(entry - slPrice);
      double minDist = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 200.0; // 20 pip
      if(slDist < minDist)
      {
         Log(StringFormat("closePast SKIP: slDist=%.5f < minDist=%.5f - attesa tick", slDist, minDist));
         closePast = false;
         if(!tickPast) return;
      }
   }

   if(g_trendBuy)
   {
      if(InpUseLongFilter && !(g_snap.close > g_snap.ma121 && g_snap.close > g_snap.ma182 && g_snap.close > g_snap.ma365))
      {
         Log(StringFormat("L2 BUY SKIP: close=%.5f sotto MA121/182/365 - trend lungo ribassista", g_snap.close));
         return;
      }
      Log(StringFormat("L2 BUY: close=%.5f bid=%.5f med=%.5f", g_snap.close, tk.bid, g_medLevel));
      if(EnterTrade(ORDER_TYPE_BUY, g_ma365SL))
         g_entryDone = true;
   }
   else if(g_trendSell)
   {
      if(InpUseLongFilter && !(g_snap.close < g_snap.ma121 && g_snap.close < g_snap.ma182 && g_snap.close < g_snap.ma365))
      {
         Log(StringFormat("L2 SELL SKIP: close=%.5f sopra MA121/182/365 - trend lungo rialzista", g_snap.close));
         return;
      }
      Log(StringFormat("L2 SELL: close=%.5f ask=%.5f med=%.5f", g_snap.close, tk.ask, g_medLevel));
      if(EnterTrade(ORDER_TYPE_SELL, g_ma365SL))
         g_entryDone = true;
   }
}

//+------------------------------------------------------------------+
//--- RIVELAZIONE NUOVA BARRA + SKIP PRIMA BARRA
//+------------------------------------------------------------------+
bool IsNewBar()
{
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == 0) return false;

   // Skip la primissima barra dopo attacco (aspetta chiusura)
   if(g_firstBarCheck == 0)
   {
      g_firstBarCheck = 1;
      g_bar0 = cur;
      Log("Prima barra rilevata. Attesa chiusura per primo segnale.");
      return false;
   }
   if(g_firstBarCheck == 1)
   {
      // Aspetta che arrivi una barra DIVERSA dalla prima
      if(cur == g_bar0) return false;
      g_firstBarCheck = 2;
      g_bar0 = cur;
      g_snap.ready = false;              // invalida cache
      g_entryDone = false;               // nuova barra → nuovo tentativo
      g_medCrossDone = false;
      Log(StringFormat("Nuova barra (prima dopo init): %s", TimeToString(cur)));
      return true;                       // segnala la prima transizione
   }

   // Normale routing
   if(cur == g_bar0) return false;
   g_bar0 = cur;
   g_snap.ready = false;
   g_entryDone = false;
   g_medCrossDone = false;
   Log(StringFormat("Nuova barra: %s", TimeToString(cur)));
   return true;
}

//+------------------------------------------------------------------+
//--- CHIUSURA AL CONTATTO CON MA365 CORRENTE (shift=0)
//+------------------------------------------------------------------+
void MonitorExit()
{
   if(!InpUseSL) return;
   if(PositionsTotal() == 0) return;

   double sl;
   if(!ReadBuf(g_slBuf, 0, sl)) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

       ulong tkt     = g_pos.Ticket();
       double open   = g_pos.PriceOpen();
       bool   hit    = false;

       if(g_pos.PositionType() == POSITION_TYPE_BUY)
          hit = (bid <= sl && sl < open);     // SL solo sotto entry
       else
          hit = (ask >= sl && sl > open);     // SL solo sopra entry

       if(!hit) continue;

      Log(StringFormat("SL #%d: %s %s=%.5f bid=%.5f ask=%.5f",
          tkt,
          (g_pos.PositionType()==POSITION_TYPE_BUY ? "BID<=MA" : "ASK>=MA"),
          MAPeriodStr(InpSL_MA), sl, bid, ask));

      if(g_trade.PositionClose(tkt))
         Log(StringFormat(">>> SL CHIUSO #%d", tkt));
      else
         Log(StringFormat(">>> ERR SL #%d: %s", tkt, ErrTxt()));
   }
}

//+------------------------------------------------------------------+
//--- CALCOLO LOTTO RISK-BASED
//+------------------------------------------------------------------+
double CalcLot(double entry, double sl)
{
   double dist = MathAbs(entry - sl);
   double minDist = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10.0;
   if(dist < minDist)
   {
      Log("CalcLot: distanza < 10 pt (" + DoubleToString(dist, _Digits) + ")");
      return 0.0;
   }

   double risk    = g_acc.Equity() * InpRiskPct / 100.0;
   if(risk <= 0.0) return 0.0;

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0)
   {
      Log("CalcLot: tickVal=" + DoubleToString(tickVal, 8) +
          " tickSize=" + DoubleToString(tickSize, 8));
      return 0.0;
   }

   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double ticks   = dist / tickSize;
   double lotRaw  = risk / (ticks * tickVal);
   double lot     = MathFloor(lotRaw / lotStep) * lotStep;
   lot = MathMax(minLot, MathMin(lot, maxLot));

   Log(StringFormat("CalcLot: eq=%.2f risk=%.2f dist=%.5f tickVal=%.5f lot=%.2f",
       g_acc.Equity(), risk, dist, tickVal, lot));

   return lot;
}

//+------------------------------------------------------------------+
//--- VERIFICA POSIZIONE ATTIVA (solo magic corrente)
//+------------------------------------------------------------------+
bool HasPosition()
{
   for(int i = 0; i < PositionsTotal(); i++)
      if(g_pos.SelectByIndex(i))
         if(g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol)
            return true;
   return false;
}

//+------------------------------------------------------------------+
//--- TARGET PROFIT SU MA3 (aggiuntivo a SL su MA365)
//+------------------------------------------------------------------+
void MonitorTP()
{
   if(!InpUseTP) return;
   if(PositionsTotal() == 0) return;

   double tp;
   if(!ReadBuf(g_tpBuf, 0, tp)) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

       ulong tkt = g_pos.Ticket();
       double open = g_pos.PriceOpen();
       bool  hit = false;

      if(g_pos.PositionType() == POSITION_TYPE_BUY)
          hit = (bid >= tp && tp > open);     // TP solo sopra entry (profitto)
       else
          hit = (ask <= tp && tp < open);     // TP solo sotto entry (profitto)

      if(!hit) continue;

      Log(StringFormat("TP #%d: %s %s=%.5f bid=%.5f ask=%.5f",
          tkt,
          (g_pos.PositionType()==POSITION_TYPE_BUY ? "BID>=MA" : "ASK<=MA"),
          MAPeriodStr(InpTP_MA), tp, bid, ask));

      if(g_trade.PositionClose(tkt))
         Log(StringFormat(">>> TP CHIUSO #%d", tkt));
      else
         Log(StringFormat(">>> ERR TP #%d: %s", tkt, ErrTxt()));
   }
}

//+------------------------------------------------------------------+
//--- EXIT SU REVERSAL DI TREND (voto cambiato segno)
//+------------------------------------------------------------------+
void MonitorMedCross()
{
   if(!InpUseMedCrossExit) return;
   if(!g_reversal) return;                  // nessun reversal in questa barra
   if(g_medCrossDone) return;               // una sola volta per reversal
   if(PositionsTotal() == 0) return;

   // reversal → chiudi tutte le posizioni aperte
   ulong tkt;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

      tkt = g_pos.Ticket();
       Log(StringFormat("MED-CROSS EXIT #%d: reversal trend (vote %+d->%+d)", tkt, g_prevVoteSum, g_voteSum));
       if(g_trade.PositionClose(tkt))
          Log(StringFormat(">>> MED-CROSS CHIUSO #%d", tkt));
       else
          Log(StringFormat(">>> ERR MED-CROSS #%d: %s", tkt, ErrTxt()));
    }
    g_medCrossDone = true;
 }

//+------------------------------------------------------------------+
//--- CHIUSURA PROATTIVA PER MARGINE
//--- sotto 150% → crisi, chiude finché non torna ≥200%
//+------------------------------------------------------------------+
void ManageMargin()
{
   if(!InpUseMargin) return;
   double ml = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   if(ml == 0.0) return;

   if(ml < InpMargTrig) g_marginCrisis = true;
   if(g_marginCrisis && ml >= InpMargTarg) g_marginCrisis = false;
   if(!g_marginCrisis) return;

   // Cerca: 1) più profittevole, 2) meno perdente
   ulong tgt = 0;
   double best = 0.0;
   bool   isProfit = false;

   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

      double p = g_pos.Profit();
      if(p > 0 && p > best)                // più profittevole
      {
         best = p; tgt = g_pos.Ticket(); isProfit = true;
      }
      if(p < 0 && (best <= 0 || p > best)) // meno perdente (più vicino a 0)
      {
         best = p; tgt = g_pos.Ticket(); isProfit = false;
      }
   }

   if(tgt > 0)
   {
      Log(StringFormat("Margin=%.0f%% (crisi <%.0f%%). Chiudo #%d (%s %.2f)",
          ml, InpMargTrig, tgt, isProfit ? "profitto" : "perdita", best));
      g_trade.PositionClose(tgt);
   }
}

//+------------------------------------------------------------------+
//--- ESEGUE ORDINE (ritorna true se aperto)
//+------------------------------------------------------------------+
bool EnterTrade(ENUM_ORDER_TYPE type, double ma365SL)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
   {
      Log("ENTER ERR: SymbolInfoTick fallito " + ErrTxt());
      return false;
   }

   double entry = (type == ORDER_TYPE_BUY) ? tk.ask : tk.bid;
   double sl    = ma365SL;
   double tp    = 0.0;

   // TP: usa MA se dalla parte giusta (profitto), altrimenti punti fissi
   if(InpUseTP)
   {
      double tpMA;
      if(ReadBuf(g_tpBuf, 0, tpMA))
      {
         bool tpValid = (type == ORDER_TYPE_BUY) ? (tpMA > entry) : (tpMA < entry);
         if(tpValid)
            tp = tpMA;
      }
      if(tp == 0.0)
      {
         double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
         tp = (type == ORDER_TYPE_BUY) ? (entry + InpFallbackTP * pt) : (entry - InpFallbackTP * pt);
         Log(StringFormat("TP fallback: %d pt (%s oltre entry %.5f)", InpFallbackTP, MAPeriodStr(InpTP_MA), entry));
      }
   }

   // Validazione direzione SL: per BUY sl < entry, per SELL sl > entry
   // Se MA365 oltre entry, SL rimosso dall'ordine e lotto su distanza virtuale
   bool slValid = (type == ORDER_TYPE_BUY) ? (sl < entry) : (sl > entry);
   if(!slValid)
   {
      Log(StringFormat("SL MA365=%.5f oltre entry=%.5f - rimosso dall'ordine", sl, entry));
      sl = 0.0;
   }

   double lot;
   if(slValid)
      lot = CalcLot(entry, ma365SL);
   else
   {
      double pipSize  = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10.0;
      double virtDist = MathMax(pipSize * 1000.0, MathAbs(entry - ma365SL));
      double virtSl   = (type == ORDER_TYPE_BUY) ? (entry - virtDist) : (entry + virtDist);
      lot = CalcLot(entry, virtSl);
   }
   if(lot <= 0.0)
   {
      Log("ENTER skip: lotto calcolato = 0");
      return false;
   }

   Log(StringFormat(">>> TENTATIVO %s: lot=%.2f entry=%.5f sl=%.5f",
       (type==ORDER_TYPE_BUY ? "BUY" : "SELL"),
       lot, entry, sl));

   if(g_trade.PositionOpen(_Symbol, type, lot, entry, sl, tp))
   {
      Log(StringFormat(">>> %s APERTO #%d",
          (type==ORDER_TYPE_BUY ? "BUY" : "SELL"),
          g_trade.ResultOrder()));
      return true;
   }

   Log(StringFormat(">>> ERR %s: retcode=%d (%s)",
       (type==ORDER_TYPE_BUY ? "BUY" : "SELL"),
       g_trade.ResultRetcode(),
       ErrTxt()));
   return false;
}

//+------------------------------------------------------------------+
//--- CHIUDI POSIZIONI DI UN TIPO (BUY/SELL)
//+------------------------------------------------------------------+
void ClosePositionsOfType(ENUM_POSITION_TYPE type)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;
      if(g_pos.PositionType() != type)     continue;

      ulong tkt = g_pos.Ticket();
      if(g_trade.PositionClose(tkt))
         Log(StringFormat(">>> FLIP CHIUSO #%d (%s)", tkt, (type==POSITION_TYPE_BUY?"BUY":"SELL")));
      else
         Log(StringFormat(">>> ERR FLIP #%d: %s", tkt, ErrTxt()));
   }
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
void OnTick()
{
   // 1) Attesa indicatore
   if(!WaitIndicator()) return;

   // 2) Nuova barra: aggiorna cache, trend, reversal + auto-close flip
   if(IsNewBar())
   {
      if(!RefreshSnapshot())
      {
         Log("SKIP: RefreshSnapshot fallito");
         return;
      }

      // MA corrente per SL (shift=0)
      if(!ReadBuf(g_slBuf, 0, g_ma365SL))
      {
         Log(StringFormat("SKIP: %s corrente non disponibile", MAPeriodStr(InpSL_MA)));
         g_snap.ready = false;
         return;
      }

      Log(StringFormat("%s corrente (shift0)=%.5f", MAPeriodStr(InpSL_MA), g_ma365SL));

      // Se trend cambiato, chiudi posizioni opposte
      if(InpUseFlipExit && g_prevTrendSell && g_trendBuy)
      {
         Log("TREND FLIP: SELL->BUY chiusura posizioni SELL");
         ClosePositionsOfType(POSITION_TYPE_SELL);
      }
      else if(InpUseFlipExit && g_prevTrendBuy && g_trendSell)
      {
         Log("TREND FLIP: BUY->SELL chiusura posizioni BUY");
         ClosePositionsOfType(POSITION_TYPE_BUY);
      }
      g_prevTrendBuy  = g_trendBuy;
      g_prevTrendSell = g_trendSell;
   }

   // 3) Monitoraggio uscite (tick-by-tick, con reversal fresco)
   MonitorExit();
   MonitorTP();
   MonitorMedCross();

   // 4) Gestione margine
   ManageMargin();

   // 5) Tick-by-tick: L2 - entry su incrocio mediana
   CheckEntry();
}
//+------------------------------------------------------------------+
