//+------------------------------------------------------------------+
//|                                                     EA_Trend.mq5 |
//|                                                        PaPP v2   |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "EA Trend - Entra nella direzione del trend (stato MA) a ogni nuova barra"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";

input group   "==========  TREND LINES  =========="
input int     InpTrendLine1    = 365;            // Linea lenta (direzione trend)
input int     InpTrendLine2    = 121;            // Linea veloce (direzione trend)

input group   "==========  EXIT CROSSOVER  =========="
input int     InpExitLine1     = 365;
input int     InpExitLine2     = 121;

input group   "==========  RISK / SL / TP  =========="
input double  InpRiskPct       = 1.0;
input bool    InpUseSL         = false;
input int     InpSL_Points     = 30;
input bool    InpUseTP         = false;
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

int      g_ind;
int      g_indD1;
int      g_bufTrend1, g_bufTrend2;
int      g_bufExit1,  g_bufExit2;
datetime g_bar0;
bool     g_ready;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

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

bool IsPriceOk(double v)
{
   return (v > 0.0 && v < 1.0e12);
}

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
         if(InpLog)
            Print(StringFormat("   DEBUG ReadBufD1(D1) buf=%d shift=%d val=%.5f",
                buf, d1Shift, val));
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

double CalcTP(ENUM_ORDER_TYPE type, double entry)
{
   if(!InpUseTP || InpTP_Points <= 0) return 0.0;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   return (type == ORDER_TYPE_BUY) ? (entry + InpTP_Points * pt)
                                   : (entry - InpTP_Points * pt);
}

double CalcSL(ENUM_ORDER_TYPE type, double entry)
{
   if(!InpUseSL || InpSL_Points <= 0) return 0.0;
   double pt = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   return (type == ORDER_TYPE_BUY) ? (entry - InpSL_Points * pt)
                                   : (entry + InpSL_Points * pt);
}

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

   double tp = CalcTP(type, entry);
   double sl = CalcSL(type, entry);

   if(InpLog)
      Print(StringFormat(">>> APERTURA TREND %s lot=%.2f entry=%.5f sl=%.5f tp=%.5f",
          (type == ORDER_TYPE_BUY ? "BUY" : "SELL"), lot, entry, sl, tp));

   if(!g_trade.PositionOpen(_Symbol, type, lot, entry, sl, tp))
   {
      if(InpLog) Print(">>> ERR TREND retcode=", g_trade.ResultRetcode());
   }
}

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
   else if(InpLog)
      Print("D1 handle OK");

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(50);
   g_trade.SetMarginMode();
   g_trade.SetAsyncMode(false);
   g_ready = false;
   g_bar0  = 0;
   g_bufTrend1 = MAPeriodToBuf(InpTrendLine1);
   g_bufTrend2 = MAPeriodToBuf(InpTrendLine2);
    g_bufExit1  = MAPeriodToBuf(InpExitLine1);
    g_bufExit2  = MAPeriodToBuf(InpExitLine2);

   if(InpLog)
       Print(StringFormat("INIT OK sym=%s tf=%s magic=%d risk=%.1f%% "
           "Trend=%s/%s Exit=%s/%s SL=%s%dp TP=%s%dp",
          _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
          InpMagic, InpRiskPct,
           MAPeriodStr(InpTrendLine1), MAPeriodStr(InpTrendLine2),
           MAPeriodStr(InpExitLine1),  MAPeriodStr(InpExitLine2),
           (InpUseSL ? "ON " : "OFF"), InpSL_Points,
           (InpUseTP ? "ON " : "OFF"), InpTP_Points));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   if(g_indD1 != INVALID_HANDLE) IndicatorRelease(g_indD1);
   if(InpLog) Print("DEINIT reason=" + IntegerToString(reason));
}

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

bool IsNewBar()
{
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == 0) return false;
   if(cur == g_bar0) return false;
   g_bar0 = cur;
   return true;
}

void OnTick()
{
   if(!WaitIndicator()) return;

   if(!IsNewBar()) return;

   // --- Legge stato attuale del trend (shift=1) ---
   double t1, t2;
   if(!ReadBufD1(g_bufTrend1, 1, t1) || !ReadBufD1(g_bufTrend2, 1, t2))
   {
      if(InpLog) Print("   TREND: LETTURA FALLITA");
      return;
   }

   int trendDir = (t1 > t2) ? POSITION_TYPE_BUY : ((t1 < t2) ? POSITION_TYPE_SELL : WRONG_VALUE);

   if(InpLog)
      Print(StringFormat("=== TREND === barra=%s %s[1]=%.5f %s[1]=%.5f -> %s",
          TimeToString(g_bar0),
          MAPeriodStr(InpTrendLine1), t1, MAPeriodStr(InpTrendLine2), t2,
          trendDir==WRONG_VALUE ? "PIATTO" : (trendDir==POSITION_TYPE_BUY ? "BUY" : "SELL")));

   // --- Legge exit crossover ---
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

   // --- Sincronizza direzione dalle posizioni reali ---
   ENUM_POSITION_TYPE realDir = WRONG_VALUE;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(g_pos.SelectByIndex(i) && g_pos.Magic() == InpMagic && g_pos.Symbol() == _Symbol)
      {
         realDir = g_pos.PositionType();
         break;
      }
    }
 
    // --- Exit crossover opposto: chiude e inverte ---
   if(exitSig >= 0 && realDir != WRONG_VALUE)
   {
      ENUM_ORDER_TYPE exitType = (exitSig == 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      ENUM_ORDER_TYPE curType = (realDir == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(exitType != curType)
         {
            if(InpLog) Print(StringFormat("   => EXIT CROSS OPPOSTO (cur=%s exit=%s) - FLIP",
                curType==ORDER_TYPE_BUY?"BUY":"SELL", exitType==ORDER_TYPE_BUY?"BUY":"SELL"));
            CloseAll();
            OpenLevel1(exitType);
            return;
         }
   }

   // --- Nessuna posizione: entra nella direzione del trend ---
   if(realDir == WRONG_VALUE)
   {
      if(trendDir == WRONG_VALUE)
      {
         if(InpLog) Print("   => TREND PIATTO - attesa...");
         return;
      }
      ENUM_ORDER_TYPE t = (trendDir == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(InpLog) Print(StringFormat("   => ENTRY TREND -> %s (Level 1)", t==ORDER_TYPE_BUY?"BUY":"SELL"));
      OpenLevel1(t);
      return;
   }

   if(InpLog) Print("   => POSIZIONE APERTA - attesa flip o TP/SL");
}
//+------------------------------------------------------------------+
