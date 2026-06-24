//+------------------------------------------------------------------+
//|                                                      EA_3gg.mq5 |
//|                                                        PaPP v2 |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "EA 3gg - Filtri MA365 + MA3, SL mediana, TP 35pt"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";
input double  InpRiskPct = 1.0;
input int     InpMagic   = 30062026;
input int     InpFiltro1 = 365;       // Filtro 1: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpFiltro2 = 3;          // Filtro 2: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpSL_MA   = 0;          // SL: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpTPpt    = 35;

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

int      g_ind, g_buf1, g_buf2, g_bufSL;
datetime g_bar0;
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
//--- MONITOR SL TICK-BY-TICK (chiude se prezzo tocca la linea SL)
//+------------------------------------------------------------------+
void MonitorSL()
{
   double slLine;
   if(!ReadBuf(g_bufSL, 0, slLine) && !ReadBuf(g_bufSL, 1, slLine)) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!g_pos.SelectByIndex(i))          continue;
      if(g_pos.Magic()  != InpMagic)       continue;
      if(g_pos.Symbol() != _Symbol)        continue;

      ulong tkt   = g_pos.Ticket();
      double open = g_pos.PriceOpen();
      bool hit    = false;

      if(g_pos.PositionType() == POSITION_TYPE_BUY)
         hit = (bid <= slLine && slLine < open);     // prezzo sceso sotto SL
      else
         hit = (ask >= slLine && slLine > open);     // prezzo salito sopra SL

      if(!hit) continue;

      Print(StringFormat("MONITOR SL #%d: %s %s=%.5f bid=%.5f ask=%.5f",
          tkt, (g_pos.PositionType()==POSITION_TYPE_BUY ? "BID<=SL" : "ASK>=SL"),
          MAPeriodStr(InpSL_MA), slLine, bid, ask));

      if(g_trade.PositionClose(tkt))
         Print(">>> SL CHIUSO #", tkt);
      else
         Print(">>> ERR SL #", tkt, " retcode=", g_trade.ResultRetcode());
   }
}

//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE type)
{
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk)) return;

   double entry = (type == ORDER_TYPE_BUY) ? tk.ask : tk.bid;

   double slLine;
   if(!ReadBuf(g_bufSL, 0, slLine) && !ReadBuf(g_bufSL, 1, slLine))
   {
      Print(StringFormat("SL %s non disponibile", MAPeriodStr(InpSL_MA)));
      return;
   }
   bool slValid = (type == ORDER_TYPE_BUY) ? (slLine < entry) : (slLine > entry);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double realDist = slValid ? MathAbs(entry - slLine) : 0.0;

   // Broker SL solo se distanza sufficiente (almeno 500 pip), altrimenti sl=0
   // La linea SL e' solo un check direzionale, non uno stop assassino
   double minSLDist = pipSize * 50.0;   // 500 pip minimi
   double sl = (slValid && realDist >= minSLDist) ? slLine : 0.0;

   double tp  = (type == ORDER_TYPE_BUY) ? (entry + InpTPpt * pt) : (entry - InpTPpt * pt);

   if(slValid && realDist < minSLDist)
      Print(StringFormat("SL %s=%.5f troppo vicino (%.0f pip < %.0f) - rimosso dall'ordine",
          MAPeriodStr(InpSL_MA), slLine, realDist / pipSize, minSLDist / pipSize));
   if(!slValid)
      Print(StringFormat("SL %s=%.5f oltre entry=%.5f - rimosso dall'ordine",
          MAPeriodStr(InpSL_MA), slLine, entry));

   // Distanza virtuale per calcolo lotto (1000 pip minimi)
   double virtDist = MathMax(pipSize * 1000.0, realDist);

   double risk = g_acc.Equity() * InpRiskPct / 100.0;
   if(risk <= 0.0) return;

   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0) return;

   double ticks  = virtDist / tickSize;
   double lotRaw = risk / (ticks * tickVal);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lot = MathFloor(lotRaw / lotStep) * lotStep;
   lot = MathMax(minLot, MathMin(lot, maxLot));
   if(lot <= 0.0) return;

   Print(StringFormat(">>> TENTATIVO %s lot=%.2f entry=%.5f sl=%s tp=%.5f "
       "realDist=%.5f virtDist=%.5f risk=%.2f",
       (type==ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry,
       sl!=0 ? DoubleToString(sl,_Digits) : "nessuno", tp,
       realDist, virtDist, risk));

   if(g_trade.PositionOpen(_Symbol, type, lot, entry, sl, tp))
      Print(">>> APERTO #", g_trade.ResultOrder(),
            " lot=", DoubleToString(lot,2));
   else
      Print(">>> ERRORE retcode=", g_trade.ResultRetcode(),
            " lot=", DoubleToString(lot,2));
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
   g_buf1  = MAPeriodToBuf(InpFiltro1);
   g_buf2  = MAPeriodToBuf(InpFiltro2);
   g_bufSL = MAPeriodToBuf(InpSL_MA);
   Print(StringFormat("INIT OK sym=%s tf=%s ind=%s magic=%d risk=%.1f%% "
       "filtro1=%s filtro2=%s SL=%s TP=%dpt",
       _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
       InpIndicatorName, InpMagic, InpRiskPct,
       MAPeriodStr(InpFiltro1), MAPeriodStr(InpFiltro2),
       MAPeriodStr(InpSL_MA), InpTPpt));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
bool g_wait = false;
void OnTick()
{
   if(!g_wait)
   {
      double tmp;
      if(!ReadBuf(BUF_MEDIAN, 1, tmp)) return;
      Print("Indicatore pronto");
      g_wait = true;
   }

   // Monitor SL su OGNI tick (chiude se prezzo tocca la linea)
   MonitorSL();

   // Nuova barra: valuta segnale e apre (senza chiudere niente)
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == g_bar0) return;
   g_bar0 = cur;

   Print(StringFormat("Nuova barra: %s", TimeToString(cur)));

   double cls, ma1, ma2;
   if(!ReadBuf(g_buf1, 1, ma1))  return;
   if(!ReadBuf(g_buf2, 1, ma2))  return;
   cls = iClose(_Symbol, _Period, 1);

   // Livello 1 = direzione (macro), Livello 2 = ingresso
   // BUY: prezzo sopra entrambi (ha rotto il livello1 in su, entra al livello2)
   // SELL: prezzo sotto entrambi (ha rotto il livello1 in giu, entra al livello2)
   bool buy  = (cls > ma1 && cls > ma2);
   bool sell = (cls < ma1 && cls < ma2);

   string s1 = (cls > ma1) ? "SU" : ((cls < ma1) ? "GIU" : "=");
   string s2 = (cls > ma2) ? "SU" : ((cls < ma2) ? "GIU" : "=");
   Print(StringFormat("SEGNALE cls=%.5f %s=%.5f(%s) %s=%.5f(%s)",
       cls, MAPeriodStr(InpFiltro1), ma1, s1,
       MAPeriodStr(InpFiltro2), ma2, s2));

   if(buy)
   {
      Print(">>> APERTURA BUY");
      OpenTrade(ORDER_TYPE_BUY);
   }
   else if(sell)
   {
      Print(">>> APERTURA SELL");
      OpenTrade(ORDER_TYPE_SELL);
   }
   else
      Print("Nessun segnale");
}
//+------------------------------------------------------------------+
