//+------------------------------------------------------------------+
//|                                                      EA_365.mq5  |
//|                                                        PaPP v2   |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "EA 365 - Breakout linea configurabile, cooldown 1 settimana, SL/TP su linee, risk %"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>

input string  InpIndicatorName = "PaPP_Median.ex5";  // Indicatore PaPP
input double  InpRiskPct       = 1.0;                // % capitale rischiata per ordine
input int     InpMagic         = 365001;             // Magic number

input group   "==========  LINEE ENTRY/SL/TP  =========="
input int     InpLinePeriod    = 365;                // Periodo linea principale (0=Median/3/7/14/30/121/182/365)
input int     InpSL_Period     = 365;                // SL: periodo MA (0=Median/3/7/14/30/121/182/365)
input int     InpTP_Period     = 3;                  // TP: periodo MA (0=Median/3/7/14/30/121/182/365)

input group   "==========  COOLDOWN  =========="
input int     InpCooldownBars  = 5;                  // Barre di cooldown dopo rottura (5D = ~1 settimana)
input bool    InpUseWeekCooldown = true;             // Usa cooldown settimanale (7 giorni calendario)

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

int      g_ind, g_bufLine, g_bufSL, g_bufTP;
datetime g_bar0;
bool     g_ready;

CTrade        g_trade;
CPositionInfo g_pos;
CAccountInfo  g_acc;

datetime g_lastBreakTime = 0;        // Timestamp ultima rottura
int      g_cooldownBars  = 0;        // Contatore barre cooldown
bool     g_waitingForDir = false;    // In attesa di direzione dopo rottura
ENUM_POSITION_TYPE g_breakDir = POSITION_TYPE_BUY;  // Direzione rottura

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
// Monitor SL tick-by-tick (chiude se prezzo tocca la linea SL)
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
         hit = (bid <= slLine && slLine < open);
      else
         hit = (ask >= slLine && slLine > open);

      if(!hit) continue;

      Print(StringFormat("MONITOR SL #%d: %s %s=%.5f bid=%.5f ask=%.5f",
          tkt, (g_pos.PositionType()==POSITION_TYPE_BUY ? "BID<=SL" : "ASK>=SL"),
          MAPeriodStr(InpSL_Period), slLine, bid, ask));

      if(g_trade.PositionClose(tkt))
         Print(">>> SL CHIUSO #", tkt);
      else
         Print(">>> ERR SL #", tkt, " retcode=", g_trade.ResultRetcode());
   }
}

//+------------------------------------------------------------------+
// Monitor TP tick-by-tick (chiude se prezzo tocca la linea TP)
void MonitorTP()
{
   double tpLine;
   if(!ReadBuf(g_bufTP, 0, tpLine) && !ReadBuf(g_bufTP, 1, tpLine)) return;

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
         hit = (bid >= tpLine && tpLine > open);
      else
         hit = (ask <= tpLine && tpLine < open);

      if(!hit) continue;

      Print(StringFormat("MONITOR TP #%d: %s %s=%.5f bid=%.5f ask=%.5f",
          tkt, (g_pos.PositionType()==POSITION_TYPE_BUY ? "BID>=TP" : "ASK<=TP"),
          MAPeriodStr(InpTP_Period), tpLine, bid, ask));

      if(g_trade.PositionClose(tkt))
         Print(">>> TP CHIUSO #", tkt);
      else
         Print(">>> ERR TP #", tkt, " retcode=", g_trade.ResultRetcode());
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
      Print(StringFormat("SL %s non disponibile", MAPeriodStr(InpSL_Period)));
      return;
   }
   bool slValid = (type == ORDER_TYPE_BUY) ? (slLine < entry) : (slLine > entry);
   double pt  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double pipSize = pt * 10.0;
   double realDist = slValid ? MathAbs(entry - slLine) : 0.0;

   double minSLDist = pipSize * 50.0;
   double sl = (slValid && realDist >= minSLDist) ? slLine : 0.0;

   double tpLine;
   double tp = 0.0;
   if(ReadBuf(g_bufTP, 0, tpLine) || ReadBuf(g_bufTP, 1, tpLine))
   {
      bool tpValid = (type == ORDER_TYPE_BUY) ? (tpLine > entry) : (tpLine < entry);
      if(tpValid) tp = tpLine;
   }
   if(tp == 0.0)
   {
      tp = (type == ORDER_TYPE_BUY) ? (entry + 35 * pt) : (entry - 35 * pt);
   }

   if(slValid && realDist < minSLDist)
      Print(StringFormat("SL %s=%.5f troppo vicino (%.0f pip < %.0f) - rimosso",
          MAPeriodStr(InpSL_Period), slLine, realDist / pipSize, minSLDist / pipSize));
   if(!slValid)
      Print(StringFormat("SL %s=%.5f oltre entry=%.5f - rimosso",
          MAPeriodStr(InpSL_Period), slLine, entry));

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
      Print(">>> APERTO #", g_trade.ResultOrder(), " lot=", DoubleToString(lot,2));
   else
      Print(">>> ERRORE retcode=", g_trade.ResultRetcode(), " lot=", DoubleToString(lot,2));
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
   g_bufLine = MAPeriodToBuf(InpLinePeriod);
   g_bufSL   = MAPeriodToBuf(InpSL_Period);
   g_bufTP   = MAPeriodToBuf(InpTP_Period);
   Print(StringFormat("INIT OK sym=%s tf=%s ind=%s magic=%d risk=%.1f%% "
       "Line=%s SL=%s TP=%s Cooldown=%d bars",
       _Symbol, EnumToString((ENUM_TIMEFRAMES)_Period),
       InpIndicatorName, InpMagic, InpRiskPct,
       MAPeriodStr(InpLinePeriod), MAPeriodStr(InpSL_Period), MAPeriodStr(InpTP_Period),
       InpCooldownBars));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   if(g_ind != INVALID_HANDLE) IndicatorRelease(g_ind);
   Print("DEINIT reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
bool WaitIndicator()
{
   if(g_ready) return true;

   double tmp;
   if(!ReadBuf(BUF_MEDIAN, 1, tmp)) return false;

   g_ready = true;
   Print("Indicatore pronto");
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
// Controlla se siamo in cooldown dopo una rottura
bool InCooldown()
{
   if(!InpUseWeekCooldown) return false;
   
   if(g_lastBreakTime == 0) return false;
   
   datetime now = TimeCurrent();
   long diffSec = now - g_lastBreakTime;
   long weekSec = 7 * 24 * 3600; // 7 giorni in secondi
   
   return (diffSec < weekSec);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!WaitIndicator()) return;

   // Monitor SL e TP su OGNI tick
   MonitorSL();
   MonitorTP();

   // Gestione cooldown su nuova barra
   if(IsNewBar())
   {
      Print(StringFormat("Nuova barra: %s", TimeToString(g_bar0)));
      
      // Decrementa cooldown barre
      if(g_cooldownBars > 0)
      {
         g_cooldownBars--;
         Print(StringFormat("Cooldown barre rimanenti: %d", g_cooldownBars));
      }
      
      // Controlla cooldown settimanale
      if(InCooldown())
      {
         Print("In cooldown settimanale - niente nuovi ordini");
         return;
      }
      
      // Resetta flag attesa direzione se cooldown finito
      if(g_cooldownBars == 0)
      {
         g_waitingForDir = false;
      }

      // Leggi valori linea principale (shift 1 = barra chiusa)
      double lineVal, closePrev, closePrev2;
      if(!ReadBuf(g_bufLine, 1, lineVal)) return;
      closePrev  = iClose(_Symbol, _Period, 1);
      closePrev2 = iClose(_Symbol, _Period, 2);
      if(!IsPriceOk(closePrev) || !IsPriceOk(closePrev2)) return;

      // Rileva rottura: close precedente era da una parte, close prima ancora dall'altra
      bool breakUp   = (closePrev > lineVal && closePrev2 <= lineVal);
      bool breakDown = (closePrev < lineVal && closePrev2 >= lineVal);

      if(breakUp || breakDown)
      {
         g_waitingForDir = true;
         g_breakDir = breakUp ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
         g_lastBreakTime = g_bar0; // timestamp barra corrente
         g_cooldownBars = InpCooldownBars;
         
         Print(StringFormat("ROTTURA %s rilevata su %s=%.5f (close=%.5f -> %.5f). Cooldown: %d barre + 1 settimana",
             (breakUp ? "SU" : "GIU"), MAPeriodStr(InpLinePeriod), lineVal, closePrev2, closePrev, InpCooldownBars));
         return; // Non apriamo subito, aspettiamo conferma direzione
      }

      // Se eravamo in attesa di direzione e cooldown barre finito, apri nella direzione della rottura
      if(g_waitingForDir && g_cooldownBars == 0 && !InCooldown())
      {
         // Verifica che il prezzo abbia confermato la direzione (stesso lato della linea)
         double lineNow, closeNow;
         if(ReadBuf(g_bufLine, 1, lineNow))
         {
            closeNow = iClose(_Symbol, _Period, 1);
            bool dirConfirmed = false;
            
            if(g_breakDir == POSITION_TYPE_BUY)
               dirConfirmed = (closeNow > lineNow);
            else
               dirConfirmed = (closeNow < lineNow);
            
            if(dirConfirmed)
            {
               Print(StringFormat("Direzione confermata %s - APERTURA", 
                   (g_breakDir==POSITION_TYPE_BUY ? "BUY" : "SELL")));
               OpenTrade(g_breakDir == POSITION_TYPE_BUY ? ORDER_TYPE_BUY : ORDER_TYPE_SELL);
               g_waitingForDir = false;
            }
            else
            {
               Print("Direzione NON confermata - annulla segnale");
               g_waitingForDir = false;
            }
         }
      }
   }
}
//+------------------------------------------------------------------+
