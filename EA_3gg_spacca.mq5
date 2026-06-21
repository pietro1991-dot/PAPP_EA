//+------------------------------------------------------------------+
//|                                                      EA_3gg.mq5 |
//|                                                        PaPP v2 |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "EA 3gg Spacca - Entra solo su rottura del secondo filtro, SL mediana, TP 35pt"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";
input double  InpRiskPct = 1.0;
input int     InpMagic   = 30062026;
input int     InpFiltro1 = 365;       // Filtro 1: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpFiltro2 = 3;          // Filtro 2: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpSL_MA   = 0;          // SL: period MA (0=Median/3/7/14/30/121/182/365)
input int     InpTP_MA   = 0;          // TP: period MA (0=Median/3/7/14/30/121/182/365, 0=disabilitato)
input bool    InpUseTP_Line = true;    // Usa linea TP (MA/Median)
input bool    InpUseTP_Points = true;  // Usa TP a punti fissi
input int     InpTPpt    = 35;         // TP in punti (fallback)

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

int      g_ind, g_buf1, g_buf2, g_bufSL, g_bufTP;
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

   // --- TP Line (MA/Median) ---
   double tpLine = 0.0;
   bool tpLineValid = false;
   if(InpUseTP_Line && g_bufTP != -1)
   {
      if(ReadBuf(g_bufTP, 0, tpLine) || ReadBuf(g_bufTP, 1, tpLine))
      {
         tpLineValid = (type == ORDER_TYPE_BUY) ? (tpLine > entry) : (tpLine < entry);
      }
   }

   // --- TP Punti fissi ---
   double tpPoints = (type == ORDER_TYPE_BUY) ? (entry + InpTPpt * pt) : (entry - InpTPpt * pt);
   bool tpPointsValid = InpUseTP_Points;

   // --- Scegli TP: priorità linea se valida, altrimenti punti ---
   double tp = 0.0;
   string tpSrc = "";
   if(InpUseTP_Line && tpLineValid)
   {
      tp = tpLine;
      tpSrc = "linea";
   }
   else if(InpUseTP_Points && tpPointsValid)
   {
      tp = tpPoints;
      tpSrc = "punti";
   }
   else if(InpUseTP_Line && !tpLineValid)
   {
      tp = tpPoints;
      tpSrc = "punti (linea invalida)";
   }
   else if(InpUseTP_Points)
   {
      tp = tpPoints;
      tpSrc = "punti";
   }
   else
   {
      Print("Nessun TP attivo (InpUseTP_Line e InpUseTP_Points entrambi false)");
      return;
   }

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

   Print(StringFormat(">>> TENTATIVO %s lot=%.2f entry=%.5f sl=%s tp=%.5f (%s) "
       "realDist=%.5f virtDist=%.5f risk=%.2f",
       (type==ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry,
       sl!=0 ? DoubleToString(sl,_Digits) : "nessuno", tp, tpSrc,
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
   g_bufTP = (InpTP_MA > 0) ? MAPeriodToBuf(InpTP_MA) : -1;
   Print(StringFormat("INIT OK sym=%s tf=%s ind=%s magic=%d risk=%.1f%% "
       "filtro1=%s filtro2=%s SL=%s TP_Line=%s TP_Points=%d",
       _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
       InpIndicatorName, InpMagic, InpRiskPct,
       MAPeriodStr(InpFiltro1), MAPeriodStr(InpFiltro2),
       MAPeriodStr(InpSL_MA),
       (InpTP_MA>0 && InpUseTP_Line) ? MAPeriodStr(InpTP_MA) : "OFF",
       InpUseTP_Points ? InpTPpt : 0));
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

   // Nuova barra: valuta rottura del secondo livello
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == g_bar0) return;
   g_bar0 = cur;

   Print(StringFormat("Nuova barra: %s", TimeToString(cur)));

   double cls1, cls2, ma1, ma2;
   if(!ReadBuf(g_buf1, 1, ma1))  return;
   if(!ReadBuf(g_buf2, 1, ma2))  return;
   cls1 = iClose(_Symbol, _Period, 1);
   cls2 = iClose(_Symbol, _Period, 2);

   // Livello 1 = direzione (macro), Livello 2 = rottura
   // Quando L2 viene rotto nella stessa direzione di L1, entriamo OPPOSTI (fade)
   bool breakUp   = (cls1 > ma2 && cls2 <= ma2);
   bool breakDown = (cls1 < ma2 && cls2 >= ma2);
   bool dirUp     = (cls1 > ma1);
   bool dirDown   = (cls1 < ma1);
   bool fadeSell  = breakUp   && dirUp;     // rottura SU + trend SU → entra SELL (fade)
   bool fadeBuy   = breakDown && dirDown;   // rottura GIU + trend GIU → entra BUY (fade)

   string s1 = dirUp ? "SU" : (dirDown ? "GIU" : "=");
   string s2 = (cls1 > ma2) ? "SU" : ((cls1 < ma2) ? "GIU" : "=");
   Print(StringFormat("SEGNALE cls1=%.5f cls2=%.5f %s=%.5f(%s) %s=%.5f(%s)",
       cls1, cls2,
       MAPeriodStr(InpFiltro1), ma1, s1,
       MAPeriodStr(InpFiltro2), ma2, s2));

   if(fadeSell)
   {
      Print(">>> APERTURA SELL (fade rottura alto)");
      OpenTrade(ORDER_TYPE_SELL);
   }
   else if(fadeBuy)
   {
      Print(">>> APERTURA BUY (fade rottura basso)");
      OpenTrade(ORDER_TYPE_BUY);
   }
   else
      Print("Nessuna rottura");
}
//+------------------------------------------------------------------+
