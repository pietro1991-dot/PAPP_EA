//+------------------------------------------------------------------+
//|                                                       PaPP_ADX.mq5 |
//|                                                        PaPP v2     |
//|  ADX classico di Wilder ANCORATO a D1: forza (ADX) + direzione    |
//|  (+DI/-DI), linea identica su ogni timeframe (firma PaPP).        |
//+------------------------------------------------------------------+
#property copyright "PHAI v2"
#property version   "1.00"
#property description "ADX Wilder ancorato a D1 (forza + direzione, uguale su ogni TF)"
#property indicator_separate_window
#property indicator_minimum 0.0
#property indicator_maximum 100.0
#property indicator_buffers 3
#property indicator_plots   3

input int   ADXPeriod = 14;
input bool  Smooth    = true;     // interpolazione intraday tra barre D1
input bool  ShowPanel = true;
input int   FontSize  = 9;

#define ANCHOR_TF PERIOD_D1

double Buff_ADX[], Buff_PDI[], Buff_MDI[];
int    hADX = INVALID_HANDLE;
int    g_d1bars = -1;
double d1ADX[], d1PDI[], d1MDI[];     // serie D1 (series-order: 0 = piu' recente)
string _pfx = "PADX_";

//+------------------------------------------------------------------+
int OnInit()
  {
   hADX = iADX(_Symbol, ANCHOR_TF, ADXPeriod);
   if(hADX==INVALID_HANDLE) return INIT_FAILED;

   SetIndexBuffer(0,Buff_ADX,INDICATOR_DATA);
   SetIndexBuffer(1,Buff_PDI,INDICATOR_DATA);
   SetIndexBuffer(2,Buff_MDI,INDICATOR_DATA);
   ArraySetAsSeries(Buff_ADX,true);
   ArraySetAsSeries(Buff_PDI,true);
   ArraySetAsSeries(Buff_MDI,true);

   PlotIndexSetInteger(0,PLOT_DRAW_TYPE,DRAW_LINE);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,clrGold);
   PlotIndexSetInteger(0,PLOT_LINE_WIDTH,3);
   PlotIndexSetString(0,PLOT_LABEL,"ADX (forza)");
   PlotIndexSetInteger(1,PLOT_DRAW_TYPE,DRAW_LINE);
   PlotIndexSetInteger(1,PLOT_LINE_COLOR,clrLimeGreen);
   PlotIndexSetString(1,PLOT_LABEL,"+DI (su)");
   PlotIndexSetInteger(2,PLOT_DRAW_TYPE,DRAW_LINE);
   PlotIndexSetInteger(2,PLOT_LINE_COLOR,clrTomato);
   PlotIndexSetString(2,PLOT_LABEL,"-DI (giu)");
   for(int p=0;p<3;p++) PlotIndexSetDouble(p,PLOT_EMPTY_VALUE,0.0);

   IndicatorSetInteger(INDICATOR_DIGITS,1);
   IndicatorSetString(INDICATOR_SHORTNAME,"PaPP ADX");
   IndicatorSetInteger(INDICATOR_LEVELS,2);
   IndicatorSetDouble(INDICATOR_LEVELVALUE,0,20.0);
   IndicatorSetDouble(INDICATOR_LEVELVALUE,1,25.0);
   IndicatorSetInteger(INDICATOR_LEVELCOLOR,0,clrDimGray);
   IndicatorSetInteger(INDICATOR_LEVELCOLOR,1,clrDimGray);
   IndicatorSetInteger(INDICATOR_LEVELSTYLE,0,STYLE_DOT);
   IndicatorSetInteger(INDICATOR_LEVELSTYLE,1,STYLE_DOT);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hADX!=INVALID_HANDLE) IndicatorRelease(hADX);
   ObjectsDeleteAll(0,_pfx);
  }

//+------------------------------------------------------------------+
double Interp(double a,double b,double f)
  {
   if(a>0 && b>0) return a+f*(b-a);
   return (b>0)?b:a;
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,const int prev_calculated,
                const datetime &time[],const double &open[],const double &high[],
                const double &low[],const double &close[],const long &tick_volume[],
                const long &volume[],const int &spread[])
  {
   if(rates_total<2) return 0;
   ArraySetAsSeries(time,true);
   int d1bars = Bars(_Symbol,ANCHOR_TF);
   if(d1bars<ADXPeriod+2) return 0;
   if(BarsCalculated(hADX)<=0) return 0;

   bool newFirst = (prev_calculated==0);
   bool newBar   = (d1bars!=g_d1bars);
   bool reload   = (newFirst || newBar);
   if(reload)
     {
      g_d1bars=d1bars;
      ArrayResize(d1ADX,d1bars); ArrayResize(d1PDI,d1bars); ArrayResize(d1MDI,d1bars);
      ArraySetAsSeries(d1ADX,true); ArraySetAsSeries(d1PDI,true); ArraySetAsSeries(d1MDI,true);
      if(CopyBuffer(hADX,0,0,d1bars,d1ADX)<=0) return 0;   // 0=ADX
      if(CopyBuffer(hADX,1,0,d1bars,d1PDI)<=0) return 0;   // 1=+DI
      if(CopyBuffer(hADX,2,0,d1bars,d1MDI)<=0) return 0;   // 2=-DI
     }
   else
     {
      double t0[],t1[],t2[];
      ArraySetAsSeries(t0,true); ArraySetAsSeries(t1,true); ArraySetAsSeries(t2,true);
      if(CopyBuffer(hADX,0,0,2,t0)>0){ d1ADX[0]=t0[0]; if(d1bars>1)d1ADX[1]=t0[1]; }
      if(CopyBuffer(hADX,1,0,2,t1)>0){ d1PDI[0]=t1[0]; if(d1bars>1)d1PDI[1]=t1[1]; }
      if(CopyBuffer(hADX,2,0,2,t2)>0){ d1MDI[0]=t2[0]; if(d1bars>1)d1MDI[1]=t2[1]; }
     }

   int from = reload ? rates_total-1 : 0;
   if(!reload)
     {
      datetime todayOpen=iTime(_Symbol,ANCHOR_TF,0);
      while(from<rates_total-1 && time[from]>=todayOpen) from++;
     }
   for(int idx=from; idx>=0; idx--)
     {
      int d1=iBarShift(_Symbol,ANCHOR_TF,time[idx],false);
      if(d1<0 || d1>=d1bars){ Buff_ADX[idx]=0;Buff_PDI[idx]=0;Buff_MDI[idx]=0; continue; }
      int prev=(d1>0)?d1-1:0;
      double f=0.0;
      if(Smooth)
        {
         datetime ta=iTime(_Symbol,ANCHOR_TF,d1);
         datetime tb=(d1>0)?iTime(_Symbol,ANCHOR_TF,d1-1):ta+PeriodSeconds(ANCHOR_TF);
         f=(tb>ta)?(double)(time[idx]-ta)/(double)(tb-ta):0.0; f=MathMax(0.0,MathMin(1.0,f));
        }
      Buff_ADX[idx]= Smooth? Interp(d1ADX[d1],d1ADX[prev],f) : d1ADX[d1];
      Buff_PDI[idx]= Smooth? Interp(d1PDI[d1],d1PDI[prev],f) : d1PDI[d1];
      Buff_MDI[idx]= Smooth? Interp(d1MDI[d1],d1MDI[prev],f) : d1MDI[d1];
     }

   if(ShowPanel && _Period!=ANCHOR_TF) DrawPanel();
   return rates_total;
  }

//+------------------------------------------------------------------+
void DrawPanel()
  {
   double adx=d1ADX[1], pdi=d1PDI[1], mdi=d1MDI[1];   // ultima D1 chiusa
   string forza = (adx<20)?"assente":((adx<25)?"debole":((adx<40)?"in sviluppo":((adx<50)?"forte":"molto forte")));
   string dir   = (pdi>mdi)?"SU":"GIU";
   color  dc    = (pdi>mdi)?clrLimeGreen:clrTomato;
   int win=ChartWindowFind(), x=10, y0=16, lh=FontSize+5;
   Lbl("T","PaPP ADX [D1-anchor]",x,y0,FontSize+1,clrGold,true,win);
   Lbl("A",StringFormat("ADX %.1f - trend %s",adx,forza),x,y0+lh,FontSize,clrGold,false,win);
   Lbl("D",StringFormat("Direzione %s  (+DI %.1f / -DI %.1f)",dir,pdi,mdi),x,y0+2*lh,FontSize,dc,true,win);
  }
//+------------------------------------------------------------------+
void Lbl(string n,string t,int x,int y,int fs,color c,bool b,int sub)
  {
   string o=_pfx+n;
   if(ObjectFind(0,o)<0) ObjectCreate(0,o,OBJ_LABEL,sub,0,0);
   ObjectSetInteger(0,o,OBJPROP_XDISTANCE,x); ObjectSetInteger(0,o,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,o,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetString(0,o,OBJPROP_TEXT,t);
   ObjectSetString(0,o,OBJPROP_FONT,b?"Consolas Bold":"Consolas");
   ObjectSetInteger(0,o,OBJPROP_FONTSIZE,fs); ObjectSetInteger(0,o,OBJPROP_COLOR,c);
   ObjectSetInteger(0,o,OBJPROP_BACK,false); ObjectSetInteger(0,o,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,o,OBJPROP_HIDDEN,true);
  }
//+------------------------------------------------------------------+
