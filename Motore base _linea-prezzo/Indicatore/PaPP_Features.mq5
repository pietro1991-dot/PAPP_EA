//+------------------------------------------------------------------+
//|                                                 PaPP_Features.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
//| Gemello di PaPP_Median, ma disegna le FEATURE DI MERCATO.        |
//| PaPP_Median  -> linee delle 7 MA + Mediana   (scala = prezzo)    |
//| PaPP_Features-> linee delle 4 feature + MEDIA (scala = 0..1)     |
//|                                                                  |
//| Le feature (Cluster/Velocity/Accel/Volatility) hanno unita' e   |
//| ordini di grandezza diversi tra loro e dal prezzo: per metterle |
//| sullo stesso grafico ognuna e' espressa come PERCENTILE (0..1)   |
//| sul proprio storico CLWIN. La linea oro = media dei 4 percentili |
//| = indice di intensita'/stress del mercato.                       |
//| Tutto ancorato a D1, come PaPP_Median -> linea uguale su ogni TF.|
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "PaPP Features - linee delle feature di mercato + media (percentili 0..1)"
#property description "Calcolo ancorato a D1 = linea uguale su ogni timeframe"
#property indicator_separate_window
#property indicator_minimum 0.0
#property indicator_maximum 100.0
#property indicator_buffers 5
#property indicator_plots   5

input int   FontSize  = 9;
input bool  Smooth    = true;       // interpolazione intraday tra barre D1
input bool  ShowPanel = true;
input color PanelBg   = C'20,20,25';

input bool  ShowCluster = true;
input bool  ShowVel     = true;
input bool  ShowAcc     = true;
input bool  ShowVol     = true;
input bool  SignedVelAcc = true;   // true: Vel/Accel attorno a 50 (sopra=su, sotto=giu); false: intensita' 0..100

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
#define MINSAMP 30          // campioni minimi nella finestra per dare un percentile

#define F_CLU 0
#define F_VEL 1
#define F_ACC 2
#define F_VOL 3
#define F_AVG 4

double Buff_Clu[], Buff_Vel[], Buff_Acc[], Buff_Vol[], Buff_Avg[];

int   gDays[7];
int   hMA[7];
int   gMAPeriods[7];
bool  g_synced=false;

color gCol[5] = {clrDeepSkyBlue, clrLimeGreen, clrOrange, clrTomato, clrGold};
string gName[5] = {"Cluster","Velocita'","Accel","Volatilita'","MEDIA"};

string _pfx  = "PF_";
string _pfx2 = "PFE_";

// Serie D1: per ogni barra D1 le 7 MA, le 4 feature grezze e i 4 percentili + media
struct D1Feat
  {
   double cols[][7];        // 7 MA per barra D1
   double rawClu[], rawVel[], rawAcc[], rawVol[];   // feature grezze (vel/acc in magnitudine)
   double sgnVel[], sgnAcc[];                        // segno (+1/-1/0) della barra per vel/acc
   double pClu[], pVel[], pAcc[], pVol[], pAvg[];    // valori PLOTTATI 0..100 (-1 = n/d)
   int    bars;
  };
D1Feat g_d1;

// snapshot barra corrente (pannello)
struct FCache { double clu,vel,acc,vol,avg; bool ok; };
FCache g_cache;

#define EMPTY (-1.0)

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

   SetIndexBuffer(F_CLU,Buff_Clu,INDICATOR_DATA);
   SetIndexBuffer(F_VEL,Buff_Vel,INDICATOR_DATA);
   SetIndexBuffer(F_ACC,Buff_Acc,INDICATOR_DATA);
   SetIndexBuffer(F_VOL,Buff_Vol,INDICATOR_DATA);
   SetIndexBuffer(F_AVG,Buff_Avg,INDICATOR_DATA);

   ArraySetAsSeries(Buff_Clu,true);
   ArraySetAsSeries(Buff_Vel,true);
   ArraySetAsSeries(Buff_Acc,true);
   ArraySetAsSeries(Buff_Vol,true);
   ArraySetAsSeries(Buff_Avg,true);

   bool show[5] = {ShowCluster,ShowVel,ShowAcc,ShowVol,true};
   int width[5] = {1,1,1,1,3};
   for(int p=0;p<5;p++)
     {
      PlotIndexSetInteger(p,PLOT_DRAW_TYPE,show[p]?DRAW_LINE:DRAW_NONE);
      PlotIndexSetInteger(p,PLOT_LINE_COLOR,gCol[p]);
      PlotIndexSetInteger(p,PLOT_LINE_WIDTH,width[p]);
      PlotIndexSetString(p,PLOT_LABEL,gName[p]);
      PlotIndexSetDouble(p,PLOT_EMPTY_VALUE,EMPTY);
     }

   IndicatorSetInteger(INDICATOR_DIGITS,1);
   IndicatorSetString(INDICATOR_SHORTNAME,"PaPP Features");

   // livelli guida (percentili 20 / 50 / 80)
   IndicatorSetInteger(INDICATOR_LEVELS,3);
   double lv[3] = {20.0,50.0,80.0};
   for(int i=0;i<3;i++)
     {
      IndicatorSetDouble(INDICATOR_LEVELVALUE,i,lv[i]);
      IndicatorSetInteger(INDICATOR_LEVELCOLOR,i,clrDimGray);
      IndicatorSetInteger(INDICATOR_LEVELSTYLE,i,STYLE_DOT);
     }
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
bool SyncMAHandles()
  {
   if(g_synced) return false;
   bool changed=false, allReady=true;
   for(int i=0;i<7;i++)
     {
      int want = TimeToBars(gDays[i]);
      if(want>gMAPeriods[i])
        {
         int h = iMA(_Symbol,ANCHOR_TF,want,0,MODE_SMA,PRICE_CLOSE);
         if(h==INVALID_HANDLE) { allReady=false; continue; }
         if(hMA[i]!=INVALID_HANDLE) IndicatorRelease(hMA[i]);
         hMA[i]=h; gMAPeriods[i]=want; changed=true;
        }
      if(BarsCalculated(hMA[i])<gMAPeriods[i]) allReady=false;
     }
   if(allReady && !changed) g_synced=true;
   return changed;
  }

//+------------------------------------------------------------------+
// Percentile di rawArr[i] nella finestra trailing [i .. i+CLWIN-1].
// rawArr in series-order (0 = barra piu' recente). Ignora EMPTY(<0).
// Ritorna -1 se i campioni validi sono < MINSAMP.
double PctlWin(double &rawArr[],int n,int i)
  {
   double cur = rawArr[i];
   if(cur<0) return EMPTY;
   int cnt=0, below=0;
   int end = MathMin(n, i+CLWIN);
   for(int k=i;k<end;k++)
     {
      double x=rawArr[k];
      if(x<0) continue;
      cnt++;
      if(x<=cur) below++;
     }
   if(cnt<MINSAMP) return EMPTY;
   return 100.0*(double)below/cnt;   // percentile in 0..100
  }

//+------------------------------------------------------------------+
// Costruisce per ogni barra D1 le feature grezze (>=0; EMPTY se non calcolabile)
void BuildRawFeatures()
  {
   int n = g_d1.bars;
   ArrayResize(g_d1.rawClu,n); ArrayResize(g_d1.rawVel,n);
   ArrayResize(g_d1.rawAcc,n); ArrayResize(g_d1.rawVol,n);
   ArrayResize(g_d1.sgnVel,n); ArrayResize(g_d1.sgnAcc,n);
   double v7[7], r[];
   ArrayResize(r,NVOL);

   for(int j=0;j<n;j++)
     {
      // Cluster: dispersione media % delle 7 MA attorno alla loro mediana
      double vcl[7]; int ccl=0;
      for(int m=0;m<7;m++){ double x=g_d1.cols[j][m]; if(IsVal(x)) vcl[ccl++]=x; }
      double clu=EMPTY;
      if(ccl>=2){ double md=MedArr(vcl,ccl); if(md>0){ double ds=0; for(int m=0;m<ccl;m++) ds+=MathAbs(vcl[m]-md)/md*100.0; clu=ds/ccl; } }
      g_d1.rawClu[j]=clu;

      // Velocity: mediana della variazione % su KSLOPE barre. rawVel = magnitudine
      // (per il percentile di intensita'); sgnVel = direzione (+su / -giu).
      double vel=EMPTY, sv=0.0;
      if(j+KSLOPE<n)
        {
         int c=0; for(int m=0;m<7;m++){ double a=g_d1.cols[j][m],b=g_d1.cols[j+KSLOPE][m]; if(IsVal(a)&&IsVal(b)) v7[c++]=(a-b)/b*100.0; }
         if(c>0){ double md=MedArr(v7,c); vel=MathAbs(md); sv=(md>0?1.0:(md<0?-1.0:0.0)); }
        }
      g_d1.rawVel[j]=vel; g_d1.sgnVel[j]=sv;

      // Acceleration: derivata seconda %. rawAcc = magnitudine; sgnAcc = direzione.
      double acc=EMPTY, sa=0.0;
      if(j+2*KSLOPE<n)
        {
         int c=0; for(int m=0;m<7;m++){ double a=g_d1.cols[j][m],b=g_d1.cols[j+KSLOPE][m],d=g_d1.cols[j+2*KSLOPE][m]; if(IsVal(a)&&IsVal(b)&&IsVal(d)) v7[c++]=(a-2.0*b+d)/d*100.0; }
         if(c>0){ double md=MedArr(v7,c); acc=MathAbs(md); sa=(md>0?1.0:(md<0?-1.0:0.0)); }
        }
      g_d1.rawAcc[j]=acc; g_d1.sgnAcc[j]=sa;

      // Volatility: mediana tra le 7 MA della dev.std dei rendimenti % su NVOL barre
      double vol=EMPTY;
      if(j+NVOL<n)
        {
         int c7=0;
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
         if(c7>0) vol=MedArr(v7,c7);
        }
      g_d1.rawVol[j]=vol;
     }
  }

//+------------------------------------------------------------------+
void BuildPercentiles()
  {
   int n = g_d1.bars;
   ArrayResize(g_d1.pClu,n); ArrayResize(g_d1.pVel,n);
   ArrayResize(g_d1.pAcc,n); ArrayResize(g_d1.pVol,n);
   ArrayResize(g_d1.pAvg,n);
   for(int j=0;j<n;j++)
     {
      // percentili di INTENSITA' (0..100) - usati per la linea MEDIA
      double pc=PctlWin(g_d1.rawClu,n,j);
      double pv=PctlWin(g_d1.rawVel,n,j);
      double pa=PctlWin(g_d1.rawAcc,n,j);
      double po=PctlWin(g_d1.rawVol,n,j);

      // media = indice di intensita'/stress (sempre su magnitudine, no segno)
      double s=0; int c=0;
      if(pc>=0){ s+=pc; c++; }
      if(pv>=0){ s+=pv; c++; }
      if(pa>=0){ s+=pa; c++; }
      if(po>=0){ s+=po; c++; }
      g_d1.pAvg[j] = (c>0)? s/c : EMPTY;

      // valori PLOTTATI: vel/acc col segno attorno a 50 (50=piatto), se richiesto
      g_d1.pClu[j]=pc;
      g_d1.pVol[j]=po;
      g_d1.pVel[j]=(pv<0)?EMPTY:(SignedVelAcc ? 50.0+0.5*g_d1.sgnVel[j]*pv : pv);
      g_d1.pAcc[j]=(pa<0)?EMPTY:(SignedVelAcc ? 50.0+0.5*g_d1.sgnAcc[j]*pa : pa);
     }
  }

//+------------------------------------------------------------------+
double Interp(double vS,double vE,double frac)
  {
   if(vS>=0 && vE>=0) return vS+frac*(vE-vS);
   if(vE>=0) return vE;
   return vS;
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
   ArraySetAsSeries(time,true);

   int d1bars = Bars(_Symbol,ANCHOR_TF);
   if(d1bars<2) return 0;
   if(BarsCalculated(hMA[0])<=0) return 0;

   bool newFirst = (prev_calculated==0);
   bool newBar   = (d1bars!=g_d1.bars);
   bool handlesChanged = (newFirst || newBar) ? SyncMAHandles() : false;
   bool reload = (newFirst || newBar || handlesChanged);

   if(reload)
     {
      g_d1.bars = d1bars;
      if(ArrayResize(g_d1.cols,d1bars)<0) return 0;
      for(int m=0;m<7;m++)
        {
         double tmp[]; ArraySetAsSeries(tmp,true);
         int got = CopyBuffer(hMA[m],0,0,d1bars,tmp);
         if(got<=0) return 0;
         for(int s=0;s<d1bars;s++) g_d1.cols[s][m] = (s<got && IsVal(tmp[s])) ? tmp[s] : 0.0;
        }
      BuildRawFeatures();
      BuildPercentiles();
     }
   else
     {
      // intraday: aggiorna solo le ultime 2 barre D1 e ricalcola la coda
      for(int m=0;m<7;m++)
        {
         double tmp[]; ArraySetAsSeries(tmp,true);
         int got = CopyBuffer(hMA[m],0,0,2,tmp);
         if(got<=0) return 0;
         g_d1.cols[0][m] = IsVal(tmp[0]) ? tmp[0] : 0.0;
         if(d1bars>1) g_d1.cols[1][m] = (got>1 && IsVal(tmp[1])) ? tmp[1] : 0.0;
        }
      BuildRawFeatures();
      BuildPercentiles();
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
         Buff_Clu[idx]=EMPTY; Buff_Vel[idx]=EMPTY; Buff_Acc[idx]=EMPTY;
         Buff_Vol[idx]=EMPTY; Buff_Avg[idx]=EMPTY;
         continue;
        }
      int prev = (d1cur>0) ? d1cur-1 : 0;
      double frac=0.0;
      if(Smooth)
        {
         datetime t0 = iTime(_Symbol,ANCHOR_TF,d1cur);
         datetime t1 = (d1cur>0) ? iTime(_Symbol,ANCHOR_TF,d1cur-1) : t0 + PeriodSeconds(ANCHOR_TF);
         frac = (t1>t0) ? (double)(time[idx]-t0)/(double)(t1-t0) : 0.0;
         frac = MathMax(0.0,MathMin(1.0,frac));
        }
      bool raw = !Smooth;
      Buff_Clu[idx] = raw ? g_d1.pClu[d1cur] : Interp(g_d1.pClu[d1cur],g_d1.pClu[prev],frac);
      Buff_Vel[idx] = raw ? g_d1.pVel[d1cur] : Interp(g_d1.pVel[d1cur],g_d1.pVel[prev],frac);
      Buff_Acc[idx] = raw ? g_d1.pAcc[d1cur] : Interp(g_d1.pAcc[d1cur],g_d1.pAcc[prev],frac);
      Buff_Vol[idx] = raw ? g_d1.pVol[d1cur] : Interp(g_d1.pVol[d1cur],g_d1.pVol[prev],frac);
      Buff_Avg[idx] = raw ? g_d1.pAvg[d1cur] : Interp(g_d1.pAvg[d1cur],g_d1.pAvg[prev],frac);
     }

   // snapshot barra corrente per pannello
   g_cache.clu=g_d1.pClu[1]; g_cache.vel=g_d1.pVel[1]; g_cache.acc=g_d1.pAcc[1];
   g_cache.vol=g_d1.pVol[1]; g_cache.avg=g_d1.pAvg[1];
   g_cache.ok = (g_cache.avg>=0);
   if(ShowPanel) DrawPanel();

   return rates_total;
  }

//+------------------------------------------------------------------+
string MagWord(double pct)
  {
   if(pct<0)  return "n/d";
   if(pct<20) return "molto basso";
   if(pct<40) return "basso";
   if(pct<60) return "normale";
   if(pct<80) return "alto";
   return "molto alto";
  }
//+------------------------------------------------------------------+
color PctC(double p)
  {
   if(p<0)  return clrGray;
   if(p<40) return clrLimeGreen;
   if(p>60) return clrTomato;
   return clrSilver;
  }
//+------------------------------------------------------------------+
// Per i valori con segno centrati a 50: parola direzione + forza.
string DirWord(double p,string up,string down)
  {
   if(p<0) return "n/d";
   double d = MathAbs(p-50.0);          // 0..50 = intensita'
   if(d<7.5) return "piatto";
   string forza = (d<20)?"lieve":((d<35)?"moderata":"forte");
   return (p>50?up:down)+" "+forza;
  }
//+------------------------------------------------------------------+
color DirC(double p)
  {
   if(p<0) return clrGray;
   if(MathAbs(p-50.0)<7.5) return clrSilver;
   return (p>50)? clrLimeGreen : clrTomato;
  }

//+------------------------------------------------------------------+
void DrawPanel()
  {
   int win = ChartWindowFind();
   int x=10,y0=18,lh=FontSize+5;
   string sT = "PaPP Features [percentili 0-100]";
   double pv[5] = {g_cache.clu,g_cache.vel,g_cache.acc,g_cache.vol,g_cache.avg};
   for(int i=0;i<5;i++)
     {
      bool signedDir = SignedVelAcc && (i==F_VEL || i==F_ACC);
      string word = signedDir ? DirWord(pv[i], (i==F_VEL)?"salita":"accel", (i==F_VEL)?"discesa":"decel")
                              : MagWord(pv[i]);
      color  col  = signedDir ? DirC(pv[i]) : ((i==F_AVG)? clrGold : PctC(pv[i]));
      string s = StringFormat("%-11s %s  (%s)", gName[i],
                              (pv[i]>=0?DoubleToString(pv[i],0):" n/d"), word);
      Lbl("L"+IntegerToString(i), s, x, y0+(i+1)*lh, FontSize, col, (i==F_AVG), win);
     }
   Lbl("T", sT, x, y0, FontSize+1, clrGold, true, win);
  }

//+------------------------------------------------------------------+
void Lbl(string n,string t,int x,int y,int fs,color c,bool b,int subwin)
  {
   string o=_pfx+n;
   if(ObjectFind(0,o)<0) ObjectCreate(0,o,OBJ_LABEL,subwin,0,0);
   ObjectSetInteger(0,o,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,o,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,o,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetString(0,o,OBJPROP_TEXT,t);
   ObjectSetString(0,o,OBJPROP_FONT,b?"Consolas Bold":"Consolas");
   ObjectSetInteger(0,o,OBJPROP_FONTSIZE,fs);
   ObjectSetInteger(0,o,OBJPROP_COLOR,c);
   ObjectSetInteger(0,o,OBJPROP_BACK,false);
   ObjectSetInteger(0,o,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,o,OBJPROP_HIDDEN,true);
  }
//+------------------------------------------------------------------+
