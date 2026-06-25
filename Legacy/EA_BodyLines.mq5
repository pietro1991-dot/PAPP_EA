//+------------------------------------------------------------------+
//|                                                  EA_BodyLines.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
//| Strategia "due linee sul corpo della candela precedente".        |
//| Ad ogni nuova candela, sul TIMEFRAME a cui l'EA e' attaccato:     |
//|   linea alta = max(open, close) candela precedente                |
//|   linea bassa = min(open, close) candela precedente               |
//|                                                                   |
//| Due modalita' (input InpMode):                                    |
//|   TREND  (segui)  : BuyStop  @linea alta , SellStop @linea bassa  |
//|                     -> compra se SFONDA in alto, vende se sfonda giu|
//|   FADE   (mean-rev): SellLimit @linea alta, BuyLimit @linea bassa |
//|                     -> vende al TOCCO dell'alto, compra al tocco basso|
//|                                                                   |
//| TP e SL in PUNTI, configurabili. Disegna le linee a schermo.      |
//|                                                                   |
//| NOTA onesta: i backtest rigorosi (vedi docs/REPORT_PATTERN_EURUSD)|
//| NON hanno trovato edge in questa famiglia. Usare in DEMO per      |
//| sperimentare, non come sistema dimostrato.                        |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Due linee sul corpo della candela precedente: TREND (segui) o FADE (mean-reversion). TP/SL in punti."

#include <Trade/Trade.mqh>

enum ENUM_STRAT_MODE
{
   MODE_TREND = 0,   // TREND - segui lo sfondamento
   MODE_FADE  = 1    // FADE  - mean reversion (vendi/compra al tocco)
};

input ENUM_STRAT_MODE InpMode        = MODE_FADE;      // Modalita'
input bool            InpUseBodyOnly  = true;          // true=corpo(open/close)  false=high/low
input int             InpTP_points    = 100;           // Take Profit in punti (0 = off)
input int             InpSL_points    = 100;           // Stop Loss in punti (0 = off)
input double          InpLot          = 0.10;          // Lotti
input bool            InpOnePosition  = true;          // Una sola posizione per volta
input bool            InpDrawLines    = true;          // Disegna le linee a schermo
input color           InpBuyColor     = clrDodgerBlue; // Colore azione BUY
input color           InpSellColor    = clrTomato;     // Colore azione SELL
input long            InpMagic        = 990011;        // Magic number

CTrade   g_trade;
string   PFX = "BL_";
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetDeviationInPoints(20);
   g_lastBar = 0;
   return(INIT_SUCCEEDED);
}
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   DeleteOurPendings();
   ObjectsDeleteAll(0, PFX);
   Comment("");
}

//+------------------------------------------------------------------+
//| Helpers prezzi SL/TP                                             |
//+------------------------------------------------------------------+
double SlBuy(double p)  { return InpSL_points>0 ? NormalizeDouble(p - InpSL_points*_Point, _Digits) : 0.0; }
double TpBuy(double p)  { return InpTP_points>0 ? NormalizeDouble(p + InpTP_points*_Point, _Digits) : 0.0; }
double SlSell(double p) { return InpSL_points>0 ? NormalizeDouble(p + InpSL_points*_Point, _Digits) : 0.0; }
double TpSell(double p) { return InpTP_points>0 ? NormalizeDouble(p - InpTP_points*_Point, _Digits) : 0.0; }

//+------------------------------------------------------------------+
bool HasOurPosition()
{
   for(int i=PositionsTotal()-1; i>=0; i--)
   {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t))
         if(PositionGetInteger(POSITION_MAGIC)==InpMagic && PositionGetString(POSITION_SYMBOL)==_Symbol)
            return true;
   }
   return false;
}
//+------------------------------------------------------------------+
void DeleteOurPendings()
{
   for(int i=OrdersTotal()-1; i>=0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(OrderSelect(t))
      {
         if(OrderGetInteger(ORDER_MAGIC)==InpMagic && OrderGetString(ORDER_SYMBOL)==_Symbol)
         {
            ENUM_ORDER_TYPE ot = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
            if(ot>=ORDER_TYPE_BUY_LIMIT)   // 2..7 = ordini pendenti
               g_trade.OrderDelete(t);
         }
      }
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   // Enforce "una posizione per volta" / OCO ad ogni tick
   if(InpOnePosition && HasOurPosition())
      DeleteOurPendings();

   // Aggiorna pannello in tempo reale
   if(InpDrawLines) UpdatePanel();

   // Agisci una volta per candela
   datetime t0 = iTime(_Symbol, _Period, 0);
   if(t0 == g_lastBar) return;
   g_lastBar = t0;

   // Candela precedente (indice 1)
   double op = iOpen (_Symbol,_Period,1);
   double cl = iClose(_Symbol,_Period,1);
   double hi = iHigh (_Symbol,_Period,1);
   double lo = iLow  (_Symbol,_Period,1);
   double up = InpUseBodyOnly ? MathMax(op,cl) : hi;
   double dn = InpUseBodyOnly ? MathMin(op,cl) : lo;

   DeleteOurPendings();                       // rinnova ad ogni candela
   if(InpDrawLines) DrawLevels(up, dn);

   if(InpOnePosition && HasOurPosition()) return;   // posizione aperta: gestita da TP/SL

   PlacePendings(up, dn);
}

//+------------------------------------------------------------------+
//| Piazza i due ordini pendenti secondo la modalita'                |
//+------------------------------------------------------------------+
void PlacePendings(double up, double dn)
{
   if(InpLot<=0) return;
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   long   sl  = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minD = (sl + 2) * _Point;           // distanza minima dal prezzo

   up = NormalizeDouble(up, _Digits);
   dn = NormalizeDouble(dn, _Digits);

   if(InpMode==MODE_TREND)
   {
      // Sfondamento: compra sopra l'alto, vendi sotto il basso
      if(up > ask + minD)
         g_trade.BuyStop (InpLot, up, _Symbol, SlBuy(up),  TpBuy(up),  ORDER_TIME_GTC, 0, "BL trend buy");
      if(dn < bid - minD)
         g_trade.SellStop(InpLot, dn, _Symbol, SlSell(dn), TpSell(dn), ORDER_TIME_GTC, 0, "BL trend sell");
   }
   else // MODE_FADE
   {
      // Mean reversion: vendi al tocco dell'alto, compra al tocco del basso
      if(up > bid + minD)
         g_trade.SellLimit(InpLot, up, _Symbol, SlSell(up), TpSell(up), ORDER_TIME_GTC, 0, "BL fade sell");
      if(dn < ask - minD)
         g_trade.BuyLimit (InpLot, dn, _Symbol, SlBuy(dn),  TpBuy(dn),  ORDER_TIME_GTC, 0, "BL fade buy");
   }
}

//+------------------------------------------------------------------+
//| Disegno linee + etichette                                        |
//+------------------------------------------------------------------+
void DrawLevels(double up, double dn)
{
   datetime t1 = iTime(_Symbol,_Period,1);
   datetime t2 = iTime(_Symbol,_Period,0) + 3*PeriodSeconds(_Period);
   // colore = azione che avviene a quella linea
   color cUp = (InpMode==MODE_TREND) ? InpBuyColor  : InpSellColor;
   color cDn = (InpMode==MODE_TREND) ? InpSellColor : InpBuyColor;
   string aUp = (InpMode==MODE_TREND) ? "BUY stop"  : "SELL limit";
   string aDn = (InpMode==MODE_TREND) ? "SELL stop" : "BUY limit";

   DrawSeg(PFX+"up", t1, up, t2, up, cUp);
   DrawSeg(PFX+"dn", t1, dn, t2, dn, cDn);
   DrawTxt(PFX+"tup", t2, up, aUp+" "+DoubleToString(up,_Digits), cUp);
   DrawTxt(PFX+"tdn", t2, dn, aDn+" "+DoubleToString(dn,_Digits), cDn);
}
//+------------------------------------------------------------------+
void DrawSeg(string name, datetime t1, double p1, datetime t2, double p2, color c)
{
   if(ObjectFind(0,name)<0)
      ObjectCreate(0,name,OBJ_TREND,0,t1,p1,t2,p2);
   ObjectSetInteger(0,name,OBJPROP_TIME,0,t1);
   ObjectSetDouble (0,name,OBJPROP_PRICE,0,p1);
   ObjectSetInteger(0,name,OBJPROP_TIME,1,t2);
   ObjectSetDouble (0,name,OBJPROP_PRICE,1,p2);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,2);
   ObjectSetInteger(0,name,OBJPROP_RAY_RIGHT,false);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,false);
}
//+------------------------------------------------------------------+
void DrawTxt(string name, datetime t, double p, string txt, color c)
{
   if(ObjectFind(0,name)<0)
      ObjectCreate(0,name,OBJ_TEXT,0,t,p);
   ObjectSetInteger(0,name,OBJPROP_TIME,0,t);
   ObjectSetDouble (0,name,OBJPROP_PRICE,0,p);
   ObjectSetString (0,name,OBJPROP_TEXT," "+txt);
   ObjectSetInteger(0,name,OBJPROP_COLOR,c);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,8);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,ANCHOR_LEFT);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
}
//+------------------------------------------------------------------+
void UpdatePanel()
{
   string mode = (InpMode==MODE_TREND) ? "TREND (segui)" : "FADE (mean-reversion)";
   string rif  = InpUseBodyOnly ? "corpo (open/close)" : "high/low";
   Comment(StringFormat("EA_BodyLines | %s | TF=%s\nRiferimento: %s candela precedente\nTP=%d pt  SL=%d pt  Lot=%.2f\nPosizione aperta: %s",
           mode, EnumToString((ENUM_TIMEFRAMES)_Period),
           rif, InpTP_points, InpSL_points, InpLot,
           HasOurPosition() ? "SI" : "no"));
}
//+------------------------------------------------------------------+
