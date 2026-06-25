//+------------------------------------------------------------------+
//|                                                   PaPP_Median.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.00"
#property description "PaPP Median - Mediana 7 MA (3g-1y)"
#property description "Calcolo ancorato a D1 = linea uguale su ogni timeframe"
#property indicator_chart_window
#property indicator_buffers 12
#property indicator_plots   8

input int   FontSize  = 9;
input bool  Smooth    = true;
input bool  ShowMA    = true;
input bool  ShowPanel = true;
input color PanelBg   = C'20,20,25';

input bool  InpSignals = false;  // true = output D1 raw (step) per crossover detection su ogni TF
input int MAPeriod1 = 365;
input int MAPeriod2 = 182;
input int MAPeriod3 = 121;
input int MAPeriod4 = 30;
input int MAPeriod5 = 14;
input int MAPeriod6 = 7;
input int MAPeriod7 = 3;

#define ANCHOR_TF PERIOD_D1
#define KSLOPE 5
#define NVOL   14
#define CLWIN  252

double Buff_Median[];
double Buff_Cluster[], Buff_Vel[], Buff_Acc[], Buff_Vol[];

struct SBuffer { double v[]; };
SBuffer gMA[7];

int   gDays[7];
color gCol[7] = {clrDodgerBlue,clrDeepSkyBlue,clrTurquoise,clrLimeGreen,clrOrange,clrTomato,clrRed};
int   hMA[7];
int   gMAPeriods[7];   // periodo effettivo in barre D1 (puo' crescere quando la history si completa)

string _pfx  = "PM_";
string _pfx2 = "PME_";

struct MetricsCache
  {
   double median, maVal[7];
   double cluCur,cluPct,velCur,velPct,accCur,accPct,volCur,volPct;
   double distHist[];
   int    distCnt,d1bars;
   double spread, spreadVel;              // Frattale: Squadra Veloce - Squadra Lenta + velocita'
  };
MetricsCache g_cache;

struct D1Data { double med[]; double cols[][7]; int bars; };
D1Data g_d1;

//+------------------------------------------------------------------+
int TimeToBars(int d)
  {
   datetime n = TimeCurrent();
   long secs = (long)d*86400;
   if(secs<=0) return 1;
   int b = 0;
   if(n>0) b = Bars(_Symbol,ANCHOR_TF,n-secs,n);
   if(b<2) b = (int)(secs/PeriodSeconds(ANCHOR_TF));
   return MathMax(1,b);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   gDays[0]=MAPeriod1; gDays[1]=MAPeriod2; gDays[2]=MAPeriod3;
   gDays[3]=MAPeriod4; gDays[4]=MAPeriod5; gDays[5]=MAPeriod6;
   gDays[6]=MAPeriod7;

   for(int i=0;i<7;i++)
     {
      gMAPeriods[i] = TimeToBars(gDays[i]);
      hMA[i] = iMA(_Symbol,ANCHOR_TF,gMAPeriods[i],0,MODE_SMA,PRICE_CLOSE);
      if(hMA[i]==INVALID_HANDLE) return INIT_FAILED;
     }

   SetIndexBuffer(0,Buff_Median,INDICATOR_DATA);
   for(int i=0;i<7;i++) SetIndexBuffer(1+i,gMA[i].v,INDICATOR_DATA);
   ArrayInitialize(Buff_Median,0.0);
   for(int i=0;i<7;i++) ArrayInitialize(gMA[i].v,0.0);
   ArraySetAsSeries(Buff_Median,true);
   for(int i=0;i<7;i++) ArraySetAsSeries(gMA[i].v,true);

   SetIndexBuffer(8,Buff_Cluster,INDICATOR_CALCULATIONS);
   SetIndexBuffer(9,Buff_Vel,INDICATOR_CALCULATIONS);
   SetIndexBuffer(10,Buff_Acc,INDICATOR_CALCULATIONS);
   SetIndexBuffer(11,Buff_Vol,INDICATOR_CALCULATIONS);
   ArrayInitialize(Buff_Cluster,0.0);
   ArrayInitialize(Buff_Vel,0.0);
   ArrayInitialize(Buff_Acc,0.0);
   ArrayInitialize(Buff_Vol,0.0);
   ArraySetAsSeries(Buff_Cluster,true);
   ArraySetAsSeries(Buff_Vel,true);
   ArraySetAsSeries(Buff_Acc,true);
   ArraySetAsSeries(Buff_Vol,true);

   PlotIndexSetInteger(0,PLOT_DRAW_TYPE,DRAW_LINE);
   PlotIndexSetInteger(0,PLOT_LINE_COLOR,clrGold);
   PlotIndexSetInteger(0,PLOT_LINE_WIDTH,2);
   PlotIndexSetString(0,PLOT_LABEL,"PaPP Median");
   PlotIndexSetDouble(0,PLOT_EMPTY_VALUE,0.0);

   for(int p=0;p<7;p++)
     {
      PlotIndexSetInteger(p+1,PLOT_DRAW_TYPE,ShowMA?DRAW_LINE:DRAW_NONE);
      PlotIndexSetInteger(p+1,PLOT_LINE_COLOR,gCol[p]);
      PlotIndexSetInteger(p+1,PLOT_LINE_WIDTH,1);
      PlotIndexSetString(p+1,PLOT_LABEL,"MA "+IntegerToString(gDays[p])+"g (~"+IntegerToString(gMAPeriods[p])+"b D1)");
      PlotIndexSetDouble(p+1,PLOT_EMPTY_VALUE,0.0);
     }

   IndicatorSetString(INDICATOR_SHORTNAME,"PaPP Median");
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   for(int i=0;i<7;i++) if(hMA[i]!=INVALID_HANDLE) IndicatorRelease(hMA[i]);
   ObjectsDeleteAll(0,_pfx);
   ObjectsDeleteAll(0,_pfx2);
  }

//+------------------------------------------------------------------+
bool IsVal(double v) { return (v>0.0 && v<1.0e12); }

//+------------------------------------------------------------------+
double MedArr(double &src[],int c)
  {
   if(c<=0) return 0;
   double a[]; ArrayResize(a,c);
   for(int j=0;j<c;j++) a[j]=src[j];
   ArraySort(a);
   if((c&1)==1) return a[c/2];
   return 0.5*(a[c/2-1]+a[c/2]);
  }

//+------------------------------------------------------------------+
double PctlOf(double &arr[],int cc,double cur)
  {
   if(cc<=0) return 0.5;
   int b=0; for(int k=0;k<cc;k++) if(arr[k]<=cur) b++;
   return (double)b/cc;
  }

//+------------------------------------------------------------------+
// Mediana delle 7 MA a barra D1 j (da g_d1.cols)
double MedOf7(int j)
  {
   double v[7]; int c=0;
   for(int m=0;m<7;m++){ double x=g_d1.cols[j][m]; if(IsVal(x)) v[c++]=x; }
   return (c>0)?MedArr(v,c):0;
  }
//+------------------------------------------------------------------+
string MagWord(double pct,string w0,string w1,string w2,string w3,string w4)
  {
   if(pct<0.20) return w0;
   if(pct<0.40) return w1;
   if(pct<0.60) return w2;
   if(pct<0.80) return w3;
   return w4;
  }
//+------------------------------------------------------------------+
string DirWord(double val,double absPct,string up,string down,string flat)
  {
   if(absPct<0.15) return flat;
   string forza = (absPct<0.40)?"lieve":((absPct<0.70)?"moderata":"forte");
   return (val>0?up:down)+" "+forza;
  }
//+------------------------------------------------------------------+
string DistWord(double val,double absPct)
  {
   if(absPct<0.15) return "sulla mediana";
   string q = (absPct<0.40)?"poco":((absPct<0.70)?"moderatamente":"molto");
   return q+(val>0?" sopra":" sotto");
  }

//+------------------------------------------------------------------+
void RefreshMetricCache()
  {
   int win = CLWIN, ext = MathMax(2*KSLOPE,NVOL+1), need = win+ext+2;
   if(g_d1.bars<need) return;

   g_cache.median = g_d1.med[1];
   for(int m=0;m<7;m++) g_cache.maVal[m] = g_d1.cols[1][m];

   // Storia delle 4 metriche su finestra CLWIN + percentile corrente
   double cA[],vA[],aA[],oA[],v7[7],r[];
   int cc=0,vc=0,ac=0,oc=0,c7;
   ArrayResize(cA,win); ArrayResize(vA,win); ArrayResize(aA,win); ArrayResize(oA,win);
   ArrayResize(r,NVOL);

   for(int j=1;j<=win;j++)
     {
      // Cluster
      double v_cl[7]; int c_cl=0;
      for(int m=0;m<7;m++){ double x=g_d1.cols[j][m]; if(IsVal(x)) v_cl[c_cl++]=x; }
      if(c_cl>=2)
        {
         double md=MedArr(v_cl,c_cl);
         if(md>0){ double ds=0; for(int m=0;m<c_cl;m++) ds+=MathAbs(v_cl[m]-md)/md*100.0; cA[cc++]=ds/c_cl; }
        }
      // Velocity
      c7=0; for(int m=0;m<7;m++){ double a=g_d1.cols[j][m],b=g_d1.cols[j+KSLOPE][m]; if(IsVal(a)&&IsVal(b)) v7[c7++]=(a-b)/b*100.0; }
      vA[vc++]=MathAbs(MedArr(v7,c7));
      // Acceleration
      c7=0; for(int m=0;m<7;m++){ double a=g_d1.cols[j][m],b=g_d1.cols[j+KSLOPE][m],d=g_d1.cols[j+2*KSLOPE][m]; if(IsVal(a)&&IsVal(b)&&IsVal(d)) v7[c7++]=(a-2.0*b+d)/d*100.0; }
      aA[ac++]=MathAbs(MedArr(v7,c7));
      // Volatility
      c7=0;
      for(int m=0;m<7;m++)
        {
         int rc=0;
         for(int t=j;t<j+NVOL;t++){ double a=g_d1.cols[t][m],b=g_d1.cols[t+1][m]; if(IsVal(a)&&IsVal(b)) r[rc++]=(a-b)/b*100.0; }
         if(rc>=2)
           {
            double mn=0; for(int q=0;q<rc;q++) mn+=r[q]; mn/=rc;
            double s=0;  for(int q=0;q<rc;q++){ double dd=r[q]-mn; s+=dd*dd; }
            v7[c7++]=MathSqrt(s/(rc-1));
           }
        }
      oA[oc++]=MedArr(v7,c7);
     }

   g_cache.cluCur=cA[0]; g_cache.velCur=vA[0]; g_cache.accCur=aA[0]; g_cache.volCur=oA[0];
   g_cache.cluPct=PctlOf(cA,cc,g_cache.cluCur);
   g_cache.velPct=PctlOf(vA,vc,MathAbs(g_cache.velCur));
   g_cache.accPct=PctlOf(aA,ac,MathAbs(g_cache.accCur));
   g_cache.volPct=PctlOf(oA,oc,g_cache.volCur);

   // --- Spread Frattale (3 veloci vs 3 lenti, esclusa MA30) ---
   // maVal[6]=MA3, [5]=MA7, [4]=MA14, [3]=MA30, [2]=MA121, [1]=MA182, [0]=MA365
   double fv = (g_cache.maVal[6] + g_cache.maVal[5] + g_cache.maVal[4]) / 3.0;  // Squadra Veloce
   double sv = (g_cache.maVal[0] + g_cache.maVal[1] + g_cache.maVal[2]) / 3.0;  // Squadra Lenta
   g_cache.spread = fv - sv;
   // Velocita': spread oggi - spread ieri (g_d1.cols[2] = barra D1-2)
   double fv_y = (g_d1.cols[2][6] + g_d1.cols[2][5] + g_d1.cols[2][4]) / 3.0;
   double sv_y = (g_d1.cols[2][0] + g_d1.cols[2][1] + g_d1.cols[2][2]) / 3.0;
   g_cache.spreadVel = g_cache.spread - (fv_y - sv_y);

   // Distance histogram
   int nd=win+2;
   double cl[]; ArraySetAsSeries(cl,true);
   if(CopyClose(_Symbol,ANCHOR_TF,0,nd,cl)!=nd) return;
   ArrayResize(g_cache.distHist,win);
   g_cache.distCnt=0;
   for(int j=1;j<=win;j++)
     {
      double md = MedOf7(j);
      if(md<=0) continue;
      g_cache.distHist[g_cache.distCnt++]=MathAbs((cl[j]-md)/md*100.0);
     }
  }

//+------------------------------------------------------------------+
double Interp(double vStart,double vEnd,double frac)
   {
    if(IsVal(vStart) && IsVal(vEnd)) return vStart+frac*(vEnd-vStart);
    if(IsVal(vEnd)) return vEnd;
    return vStart;
   }

//+------------------------------------------------------------------+
// Ricrea gli handle MA quando la history D1 si e' completata e il periodo
// reale (in barre) e' cambiato rispetto a quello fissato in OnInit.
// Risolve il caso "chart appena aperto": all'init la history puo' essere
// incompleta -> periodo troppo corto, qui lo si corregge appena cresce.
// Ritorna true se almeno un handle e' stato ricreato (forza full reload).
bool SyncMAHandles()
  {
   bool changed=false;
   for(int i=0;i<7;i++)
     {
      int want = TimeToBars(gDays[i]);
      if(want==gMAPeriods[i]) continue;
      int h = iMA(_Symbol,ANCHOR_TF,want,0,MODE_SMA,PRICE_CLOSE);
      if(h==INVALID_HANDLE) continue;              // riprova al prossimo tick
      if(hMA[i]!=INVALID_HANDLE) IndicatorRelease(hMA[i]);
      hMA[i]=h; gMAPeriods[i]=want; changed=true;
     }
   return changed;
  }

//+------------------------------------------------------------------+
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total<2) { Print(__FUNCTION__,": rates_total<2 (insufficient data)"); return 0; }
   ArraySetAsSeries(close,true);
   ArraySetAsSeries(time,true);

   int d1bars = Bars(_Symbol,ANCHOR_TF);
    if(d1bars<2) { Print(__FUNCTION__,": d1bars<2"); return 0; }
   if(BarsCalculated(hMA[0])<=0) { Print(__FUNCTION__,": MA not ready"); return 0; }

    bool newFirst = (prev_calculated==0);
   bool newBar   = (d1bars!=g_d1.bars);
   // La history D1 cresce a tick durante il caricamento: ad ogni cambio
   // (newBar) ricontrolla i periodi MA e ricrea gli handle se necessario.
   bool handlesChanged = (newFirst || newBar) ? SyncMAHandles() : false;
   bool reload = (newFirst || newBar || handlesChanged);
   if(reload)
     {
      g_d1.bars = d1bars;
      // Full reload su ogni nuova barra D1 (Claude fix)
      if(ArrayResize(g_d1.med,d1bars)<0) return 0;
      ArraySetAsSeries(g_d1.med,true);
      if(ArrayResize(g_d1.cols,d1bars)<0) return 0;
      for(int m=0;m<7;m++)
        {
         double tmp[]; ArraySetAsSeries(tmp,true);
         int got = CopyBuffer(hMA[m],0,0,d1bars,tmp);
         if(got<=0) return 0;
          for(int s=0;s<d1bars;s++) g_d1.cols[s][m] = (s<got && IsVal(tmp[s])) ? tmp[s] : 0.0;
        }
      for(int s=0;s<d1bars;s++) g_d1.med[s] = MedOf7(s);
     }
   else
     {
      // Intraday stesso D1: copia solo le ultime 2 barre D1
      for(int m=0;m<7;m++)
        {
         double tmp[]; ArraySetAsSeries(tmp,true);
         int got = CopyBuffer(hMA[m],0,0,2,tmp);
         if(got<=0) return 0;
          g_d1.cols[0][m] = IsVal(tmp[0]) ? tmp[0] : 0.0;
          if(d1bars>1) g_d1.cols[1][m] = (got>1 && IsVal(tmp[1])) ? tmp[1] : 0.0;
        }
      for(int s=0;s<MathMin(2,d1bars);s++) g_d1.med[s] = MedOf7(s);
     }

   int recalcFrom;
   if(reload)
      recalcFrom = rates_total-1;
   else
     {
      datetime todayOpen = iTime(_Symbol,ANCHOR_TF,0);
      recalcFrom = 0;
      while(recalcFrom < rates_total-1 && time[recalcFrom] >= todayOpen) recalcFrom++;
     }

   for(int idx=recalcFrom; idx>=0; idx--)
     {
      int d1cur = iBarShift(_Symbol,ANCHOR_TF,time[idx],false);
      if(d1cur<0 || d1cur>=d1bars)
        {
         Buff_Median[idx]=0;
         for(int m=0;m<7;m++) gMA[m].v[idx]=0.0;
         continue;
        }

      int sj = d1cur;
      double frac=0.0;
      if(Smooth)
        {
         datetime t0 = iTime(_Symbol,ANCHOR_TF,d1cur);
         datetime t1 = (d1cur>0) ? iTime(_Symbol,ANCHOR_TF,d1cur-1)
                                 : t0 + PeriodSeconds(ANCHOR_TF);
         frac = (t1>t0) ? (double)(time[idx]-t0)/(double)(t1-t0) : 0.0;
         frac = MathMax(0.0,MathMin(1.0,frac));
        }

      int prev = (d1cur>0) ? d1cur-1 : 0;

       bool useRaw = (InpSignals || !Smooth);
       if(useRaw)
          Buff_Median[idx] = (sj<d1bars && IsVal(g_d1.med[sj])) ? g_d1.med[sj] : 0.0;
       else
         {
          double vS  = (sj<d1bars && IsVal(g_d1.med[sj]))   ? g_d1.med[sj]   : 0.0;
          double vE  = IsVal(g_d1.med[prev])                ? g_d1.med[prev]  : 0.0;
          Buff_Median[idx] = Interp(vS,vE,frac);
         }

       for(int m=0;m<7;m++)
         {
          double val;
          if(useRaw)
             val = (sj<d1bars && IsVal(g_d1.cols[sj][m])) ? g_d1.cols[sj][m] : 0.0;
          else
            {
             double vS2 = (sj<d1bars && IsVal(g_d1.cols[sj][m])) ? g_d1.cols[sj][m] : 0.0;
             double vE2 = IsVal(g_d1.cols[prev][m])              ? g_d1.cols[prev][m] : 0.0;
             val = Interp(vS2,vE2,frac);
            }
          gMA[m].v[idx] = val;
         }
      }

   if(g_cache.d1bars!=d1bars || handlesChanged) { g_cache.d1bars=d1bars; RefreshMetricCache(); }
   Buff_Cluster[0]=g_cache.cluCur; Buff_Vel[0]=g_cache.velCur;
   Buff_Acc[0]=g_cache.accCur;     Buff_Vol[0]=g_cache.volCur;
   if(_Period != PERIOD_D1) { DrawInfo(); DrawTags(time[0]); }
   return rates_total;
  }

//+------------------------------------------------------------------+
int TxtW(string s,int fs,bool bold)
  {
   TextSetFont(bold?"Consolas Bold":"Consolas",-fs*10);
   uint w=0,h=0;
   bool ok=TextGetSize(s,w,h);
   int est=(int)MathCeil(StringLen(s)*fs*0.62);
   if(!ok || (int)w<=0) return est;
   return MathMax((int)w,est);
  }
//+------------------------------------------------------------------+
void DrawInfo()
  {
   double bid = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(g_cache.median<=0) return;

   double distPct = (bid-g_cache.median)/g_cache.median*100;
   double distAbsPct = PctlOf(g_cache.distHist,g_cache.distCnt,MathAbs(distPct));
   color distC = (distPct>0)?clrRed:clrLimeGreen;

   int x=10,y0=30,lh=FontSize+4;

   string sT  = "PaPP Median ["+StringSubstr(EnumToString((ENUM_TIMEFRAMES)_Period),7)+"]";
   string sM  = "Median: "+DoubleToString(g_cache.median,_Digits);
   string sD  = StringFormat("Dist: %+.2f%% - %s (P%.0f)",distPct,DistWord(distPct,distAbsPct),distAbsPct*100);
   string sV  = StringFormat("Cluster %.3f%% - %s (P%.0f)",g_cache.cluCur,MagWord(g_cache.cluPct,"molto stretto","stretto","normale","largo","molto largo"),g_cache.cluPct*100);
   string sVE = StringFormat("Velocita' %+.3f%% - %s",g_cache.velCur,DirWord(g_cache.velCur,g_cache.velPct,"in salita","in discesa","quasi piatta"));
   string sAC = StringFormat("Accel %+.4f%% - %s",g_cache.accCur,DirWord(g_cache.accCur,g_cache.accPct,"in accelerazione","in decelerazione","stabile"));
   string sVO = StringFormat("Volatilita' %.4f%% - %s (P%.0f)",g_cache.volCur,MagWord(g_cache.volPct,"molto bassa","bassa","normale","alta","molto alta"),g_cache.volPct*100);
   string sMA[7];
   for(int m=0;m<7;m++) sMA[m]=StringFormat("MA %3dg (%d b): %s",gDays[m],gMAPeriods[m],DoubleToString(g_cache.maVal[m],_Digits));
   string sH  = "Sopra=SELL | Sotto=BUY";

   // Frattale
   string trendF = (g_cache.spread > 0.00001) ? "BULLISH" : ((g_cache.spread < -0.00001) ? "BEARISH" : "NEUTRO");
   string sF   = StringFormat("Frattale: %+.6f (vel %+.6f) %s", g_cache.spread, g_cache.spreadVel, trendF);

   int maxw=0;
   maxw=MathMax(maxw,TxtW(sT,FontSize+2,true));
   maxw=MathMax(maxw,TxtW(sM,FontSize,false));
   maxw=MathMax(maxw,TxtW(sD,FontSize,true));
   maxw=MathMax(maxw,TxtW(sV,FontSize,false));
   maxw=MathMax(maxw,TxtW(sVE,FontSize,false));
   maxw=MathMax(maxw,TxtW(sAC,FontSize,false));
   maxw=MathMax(maxw,TxtW(sVO,FontSize,false));
   maxw=MathMax(maxw,TxtW(sF,FontSize,true));
   maxw=MathMax(maxw,TxtW(sH,FontSize-1,false));
   for(int m=0;m<7;m++) maxw=MathMax(maxw,TxtW(sMA[m],FontSize-1,false));
   int boxX=x-6, boxY=y0-6;
   int w=maxw+(x-boxX)+10;
   int bodyH=16*lh+6;
   PanelBox(boxX,boxY,w,bodyH);

   int y=y0;
   Lbl("T",sT,x,y,FontSize+2,clrGold,true); y+=lh+4;
   Lbl("M",sM,x,y,FontSize,clrGold,false);  y+=lh;
   Lbl("D",sD,x,y,FontSize,distC,true);     y+=lh+2;
   Lbl("V",sV,x,y,FontSize,(g_cache.cluPct<0.40)?clrLimeGreen:((g_cache.cluPct>0.60)?clrTomato:clrSilver),false); y+=lh;
   Lbl("VEL",sVE,x,y,FontSize,(g_cache.velCur>0)?clrLimeGreen:clrTomato,false); y+=lh;
   Lbl("ACC",sAC,x,y,FontSize,(g_cache.accCur>0)?clrLimeGreen:clrTomato,false); y+=lh;
    Lbl("VOL",sVO,x,y,FontSize,(g_cache.volPct<0.40)?clrLimeGreen:((g_cache.volPct>0.60)?clrTomato:clrAqua),false); y+=lh+2;
    Lbl("F",sF,x,y,FontSize,(g_cache.spread>0)?clrLimeGreen:clrTomato,true); y+=lh+2;
   for(int m=0;m<7;m++)
     {
      Lbl("a"+IntegerToString(m),sMA[m],x,y,FontSize-1,(g_cache.maVal[m]>0)?gCol[m]:clrGray,false);
      y+=lh-2;
     }
   y+=2;
   Lbl("H",sH,x,y,FontSize-1,clrGray,false);
  }

//+------------------------------------------------------------------+
void Tag(string n,datetime t,double price,string txt,color c)
  {
   string o=_pfx2+n;
   if(price<=0) { ObjectDelete(0,o); return; }
   if(ObjectFind(0,o)<0) ObjectCreate(0,o,OBJ_TEXT,0,0,0);
   ObjectSetInteger(0,o,OBJPROP_TIME,t);
   ObjectSetDouble(0,o,OBJPROP_PRICE,price);
   ObjectSetString(0,o,OBJPROP_TEXT," "+txt);
   ObjectSetString(0,o,OBJPROP_FONT,"Consolas");
   ObjectSetInteger(0,o,OBJPROP_FONTSIZE,FontSize);
   ObjectSetInteger(0,o,OBJPROP_COLOR,c);
   ObjectSetInteger(0,o,OBJPROP_ANCHOR,ANCHOR_LEFT);
   ObjectSetInteger(0,o,OBJPROP_BACK,false);
   ObjectSetInteger(0,o,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,o,OBJPROP_HIDDEN,true);
  }

//+------------------------------------------------------------------+
void DrawTags(datetime tlast)
  {
   datetime tfut = tlast + 2*PeriodSeconds(_Period);
   Tag("med",tfut,Buff_Median[0],"Mediana",clrGold);
   for(int m=0;m<7;m++)
     {
      double p = ShowMA ? gMA[m].v[0] : 0.0;
      Tag(IntegerToString(m),tfut,p,IntegerToString(gDays[m])+"g",gCol[m]);
     }
  }

//+------------------------------------------------------------------+
void Lbl(string n,string t,int x,int y,int fs,color c,bool b)
  {
   string o=_pfx+n;
   if(ObjectFind(0,o)<0) ObjectCreate(0,o,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,o,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,o,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,o,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetString(0,o,OBJPROP_TEXT,t);
   ObjectSetString(0,o,OBJPROP_FONT,b?"Consolas Bold":"Consolas");
   ObjectSetInteger(0,o,OBJPROP_FONTSIZE,fs);
   ObjectSetInteger(0,o,OBJPROP_COLOR,c);
   ObjectSetInteger(0,o,OBJPROP_BACK,false);
   ObjectSetInteger(0,o,OBJPROP_ZORDER,1);
   ObjectSetInteger(0,o,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,o,OBJPROP_HIDDEN,true);
  }
//+------------------------------------------------------------------+
void PanelBox(int px,int py,int w,int h)
  {
   string o=_pfx+"BOX";
   if(!ShowPanel) { ObjectDelete(0,o); return; }
   if(ObjectFind(0,o)<0) ObjectCreate(0,o,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,o,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,o,OBJPROP_XDISTANCE,px);
   ObjectSetInteger(0,o,OBJPROP_YDISTANCE,py);
   ObjectSetInteger(0,o,OBJPROP_XSIZE,w);
   ObjectSetInteger(0,o,OBJPROP_YSIZE,h);
   ObjectSetInteger(0,o,OBJPROP_BGCOLOR,PanelBg);
   ObjectSetInteger(0,o,OBJPROP_BORDER_TYPE,BORDER_FLAT);
   ObjectSetInteger(0,o,OBJPROP_COLOR,clrDimGray);
   ObjectSetInteger(0,o,OBJPROP_BACK,false);
   ObjectSetInteger(0,o,OBJPROP_ZORDER,0);
   ObjectSetInteger(0,o,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,o,OBJPROP_HIDDEN,true);
  }
//+------------------------------------------------------------------+
