//+------------------------------------------------------------------+
//|                                              PaPP_Projection.mq5 |
//|                                                        PaPP v2 |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.01"
#property description "Proietta MA + Mediana in avanti"
#property description "Regr. lineare su chiusure D1 -> simula chiusure future -> ricalcola SMA"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots 0

input int    InpTrendDays = 10;     // barre D1 per regressione (>=5)
input int    InpProjDays  = 21;     // giorni da proiettare (>=1)
input bool   InpShowMed   = true;   // mostra mediana proiettata
input bool   InpShowMA    = true;   // mostra MA proiettate
input bool   InpShowCI    = true;   // mostra fascia confidenza 68%
input bool   InpShowInfo  = true;   // mostra info nel pannello
input string InpIndiName  = "PaPP_Median.ex5";  // indicatore metriche

#define ANCHOR_TF PERIOD_D1
#define N_MA 7
#define HIST_EXTRA 400
#define PPRFX "PPROJ_"

int    g_per[N_MA]={365,182,121,30,14,7,3};
color  g_col[N_MA]={clrDodgerBlue,clrDeepSkyBlue,clrTurquoise,
                    clrLimeGreen,clrOrange,clrTomato,clrRed};
int    g_hIndi = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
{
   g_hIndi = iCustom(_Symbol,_Period,InpIndiName);
   if(g_hIndi==INVALID_HANDLE) Print("PaPP Proj: ",InpIndiName," non trovato");
   for(int i=0;i<N_MA;i++) { ObjectDelete(0,PPRFX+IntegerToString(g_per[i])); ObjectDelete(0,PPRFX+"U"+IntegerToString(g_per[i])); ObjectDelete(0,PPRFX+"L"+IntegerToString(g_per[i])); }
   ObjectDelete(0,PPRFX+"MED"); ObjectDelete(0,PPRFX+"UMED"); ObjectDelete(0,PPRFX+"LMED");
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int)
{
   if(g_hIndi!=INVALID_HANDLE) IndicatorRelease(g_hIndi);
   for(int i=0;i<N_MA;i++) { ObjectDelete(0,PPRFX+IntegerToString(g_per[i])); ObjectDelete(0,PPRFX+"U"+IntegerToString(g_per[i])); ObjectDelete(0,PPRFX+"L"+IntegerToString(g_per[i])); }
   ObjectDelete(0,PPRFX+"MED"); ObjectDelete(0,PPRFX+"UMED"); ObjectDelete(0,PPRFX+"LMED");
}

//+------------------------------------------------------------------+
void DrawTrend(string nm,datetime t1,double p1,datetime t2,double p2,color clr,int style,int width,bool back)
{
   if(ObjectFind(0,nm)<0)
      ObjectCreate(0,nm,OBJ_TREND,0,t1,p1,t2,p2);
   else
   {
      ObjectSetInteger(0,nm,OBJPROP_TIME,0,t1);
      ObjectSetDouble(0,nm,OBJPROP_PRICE,0,p1);
      ObjectSetInteger(0,nm,OBJPROP_TIME,1,t2);
      ObjectSetDouble(0,nm,OBJPROP_PRICE,1,p2);
   }
   ObjectSetInteger(0,nm,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,nm,OBJPROP_STYLE,style);
   ObjectSetInteger(0,nm,OBJPROP_WIDTH,width);
   ObjectSetInteger(0,nm,OBJPROP_RAY,false);
   ObjectSetInteger(0,nm,OBJPROP_BACK,back);
   ObjectSetInteger(0,nm,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,nm,OBJPROP_HIDDEN,true);
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
   if(rates_total<2) return 0;
   if(InpProjDays<1 || InpTrendDays<5) return 0;

   static datetime lastD1=0;
   datetime d1now=iTime(_Symbol,ANCHOR_TF,0);
   if(d1now==0) return 0;
   if(d1now==lastD1) return rates_total;
   lastD1=d1now;

   int d1bars=Bars(_Symbol,ANCHOR_TF);
   if(d1bars<g_per[0]) { Comment("PaPP Proj: dati D1 insufficienti"); return 0; }

   int need=HIST_EXTRA+InpProjDays;
   int nHist=MathMin(d1bars,need);
   double dc[];
   ArraySetAsSeries(dc,true);
   int got=CopyClose(_Symbol,ANCHOR_TF,0,nHist,dc);
   if(got<g_per[0]-InpProjDays) return 0;

   // Regressione lineare
   int regN=MathMin(InpTrendDays,got);
   double sx=0,sy=0,sxy=0,sx2=0;
   for(int i=0;i<regN;i++){ double x=-i,y=dc[i]; sx+=x; sy+=y; sxy+=x*y; sx2+=x*x; }
   double denom=regN*sx2-sx*sx;
   double slope=(denom==0)?0:(regN*sxy-sx*sy)/denom;
   double inter=(denom==0)?sy/regN:(sy-slope*sx)/regN;

   // Errore standard della regressione
   double x_mean=-(regN-1)/2.0;
   double Sxx=0, se2=0;
   for(int i=0;i<regN;i++){ double x=-i; Sxx+=(x-x_mean)*(x-x_mean); double e=dc[i]-(inter+slope*x); se2+=e*e; }
   double se=MathSqrt(se2/(regN-2));

   // Build close array
   int arrSize=HIST_EXTRA+InpProjDays+1;
   double ca[], caU[], caL[];
   if(ArrayResize(ca,arrSize)<0 || ArrayResize(caU,arrSize)<0 || ArrayResize(caL,arrSize)<0) return 0;
   for(int i=0;i<=HIST_EXTRA;i++)
   {
      double cv=(i<got)?dc[i]:dc[got-1];
      ca[HIST_EXTRA-i]=cv;
      caU[HIST_EXTRA-i]=cv;
      caL[HIST_EXTRA-i]=cv;
   }
   for(int t=1;t<=InpProjDays;t++)
   {
      double f=inter+slope*t;      // projected close
      double x_pred=t;
      double ci=se*MathSqrt(1+1.0/regN+(x_pred-x_mean)*(x_pred-x_mean)/Sxx);
      ca[HIST_EXTRA+t]=f;
      caU[HIST_EXTRA+t]=f+ci;
      caL[HIST_EXTRA+t]=f-ci;
   }

   // SMA + mediana per centrale, upper, lower
   double ma[][N_MA], maU[][N_MA], maL[][N_MA];
   double med[], medU[], medL[];
   if(ArrayResize(ma,InpProjDays+1)<0 || ArrayResize(maU,InpProjDays+1)<0 || ArrayResize(maL,InpProjDays+1)<0) return 0;
   if(ArrayResize(med,InpProjDays+1)<0 || ArrayResize(medU,InpProjDays+1)<0 || ArrayResize(medL,InpProjDays+1)<0) return 0;

   for(int t=0;t<=InpProjDays;t++)
   {
      for(int m=0;m<N_MA;m++)
      {
         double s=0,sU=0,sL=0;
         int base=HIST_EXTRA+t;
         int cnt=g_per[m];
         for(int i=0;i<cnt;i++)
         {
            s+=ca[base-i];
            sU+=caU[base-i];
            sL+=caL[base-i];
         }
         ma[t][m]=s/cnt; maU[t][m]=sU/cnt; maL[t][m]=sL/cnt;
      }
      double tmp[N_MA], tmpU[N_MA], tmpL[N_MA];
      for(int m=0;m<N_MA;m++){ tmp[m]=ma[t][m]; tmpU[m]=maU[t][m]; tmpL[m]=maL[t][m]; }
      ArraySort(tmp); ArraySort(tmpU); ArraySort(tmpL);
      int mid=(N_MA&1)?N_MA/2:0;
      med[t]=(N_MA&1)?tmp[mid]:0.5*(tmp[mid-1]+tmp[mid]);
      medU[t]=(N_MA&1)?tmpU[mid]:0.5*(tmpU[mid-1]+tmpU[mid]);
      medL[t]=(N_MA&1)?tmpL[mid]:0.5*(tmpL[mid-1]+tmpL[mid]);
   }

   datetime tStart=iTime(_Symbol,_Period,0);
   datetime tEnd=tStart+InpProjDays*PeriodSeconds(ANCHOR_TF);

   // Mediana + fascia confidenza
   if(InpShowMed)
   {
      DrawTrend(PPRFX+"MED",tStart,med[0],tEnd,med[InpProjDays],clrGold,STYLE_DASH,2,true);
      if(InpShowCI)
      {
         DrawTrend(PPRFX+"UMED",tStart,medU[0],tEnd,medU[InpProjDays],clrGold,STYLE_DOT,1,true);
         DrawTrend(PPRFX+"LMED",tStart,medL[0],tEnd,medL[InpProjDays],clrGold,STYLE_DOT,1,true);
      }
   }

   // MA + fascia confidenza
   if(InpShowMA)
   {
      for(int m=0;m<N_MA;m++)
      {
         string nm=PPRFX+IntegerToString(g_per[m]);
         DrawTrend(nm,tStart,ma[0][m],tEnd,ma[InpProjDays][m],g_col[m],STYLE_DOT,1,true);
         if(InpShowCI)
         {
            DrawTrend(PPRFX+"U"+IntegerToString(g_per[m]),tStart,maU[0][m],tEnd,maU[InpProjDays][m],g_col[m],STYLE_DOT,1,true);
            DrawTrend(PPRFX+"L"+IntegerToString(g_per[m]),tStart,maL[0][m],tEnd,maL[InpProjDays][m],g_col[m],STYLE_DOT,1,true);
         }
      }
   }

   if(InpShowInfo)
   {
      double clu=0,vel=0,acc=0,vol=0;
      if(g_hIndi!=INVALID_HANDLE)
      {
         double tmp[1];
         if(CopyBuffer(g_hIndi,8,0,1,tmp)==1) clu=tmp[0];
         if(CopyBuffer(g_hIndi,9,0,1,tmp)==1) vel=tmp[0];
         if(CopyBuffer(g_hIndi,10,0,1,tmp)==1) acc=tmp[0];
         if(CopyBuffer(g_hIndi,11,0,1,tmp)==1) vol=tmp[0];
      }
      Comment(StringFormat("PaPP Proj: pend D1 %+.5f (%+.2fpt/gg) | %dgg: Med %+.2f%% [%+.2f%%,%+.2f%%]  |  Cluster %.2f%% Vel %.4f%% Acc %.4f%% Vol %.4f%%",
          slope, slope/_Point, InpProjDays,
          (med[InpProjDays]/med[0]-1)*100,
          (medL[InpProjDays]/med[0]-1)*100,
          (medU[InpProjDays]/med[0]-1)*100,
          clu, vel, acc, vol));
   }

   return rates_total;
}
