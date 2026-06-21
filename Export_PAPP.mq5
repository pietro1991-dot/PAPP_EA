//+------------------------------------------------------------------+
//|                                                   Export_PAPP.mq5 |
//|                                                        PaPP v2 |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.00"
#property description "Esporta D1-anchor MA + tutte le metriche PaPP in CSV"

#include <Trade\Trade.mqh>

input string InpIndicatorName = "PaPP_Median.ex5";
input string InpStartDate     = "2024.01.01";
input string InpEndDate       = "2026.06.20";
input string InpFileName      = "PAPP_Export.csv";

#define BUF_MEDIAN  0
#define BUF_MA365   1
#define BUF_MA182   2
#define BUF_MA121   3
#define BUF_MA30    4
#define BUF_MA14    5
#define BUF_MA7     6
#define BUF_MA3     7

#define ANCHOR_TF PERIOD_D1
#define KSLOPE 5
#define NVOL   14
#define CLWIN  252

int      g_ind;
int      g_hMA[7];          // handle MA su D1
int      g_per[7] = {365,182,121,30,14,7,3};
datetime g_startTime, g_endTime;
bool     g_done = false;

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
bool IsPriceOk(double v) { return (v>0.0 && v<1.0e12); }

//+------------------------------------------------------------------+
bool ReadBuf(int buf, int shift, double &val)
{
   double tmp[1];
   if(CopyBuffer(g_ind,buf,shift,1,tmp)!=1) return false;
   val=tmp[0];
   return IsPriceOk(val);
}

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
bool LoadBuffers(
   double &o[], double &h[], double &l[], double &c[], datetime &t[],
   double &bM[], double &b365[], double &b182[], double &b121[],
   double &b30[], double &b14[], double &b7[], double &b3[],
   int totalBars)
{
   ArraySetAsSeries(o,true);ArraySetAsSeries(h,true);ArraySetAsSeries(l,true);
   ArraySetAsSeries(c,true);ArraySetAsSeries(t,true);
   int nO=CopyOpen(_Symbol,_Period,0,totalBars,o);
   int nH=CopyHigh(_Symbol,_Period,0,totalBars,h);
   int nL=CopyLow(_Symbol,_Period,0,totalBars,l);
   int nC=CopyClose(_Symbol,_Period,0,totalBars,c);
   int nT=CopyTime(_Symbol,_Period,0,totalBars,t);
   int maxBar=nO;
   if(nH<maxBar) maxBar=nH; if(nL<maxBar) maxBar=nL;
   if(nC<maxBar) maxBar=nC; if(nT<maxBar) maxBar=nT;

   ArraySetAsSeries(bM,true);ArraySetAsSeries(b365,true);ArraySetAsSeries(b182,true);
   ArraySetAsSeries(b121,true);ArraySetAsSeries(b30,true);ArraySetAsSeries(b14,true);
   ArraySetAsSeries(b7,true);ArraySetAsSeries(b3,true);
   int nM=CopyBuffer(g_ind,BUF_MEDIAN,0,totalBars,bM);
   int n365=CopyBuffer(g_ind,BUF_MA365,0,totalBars,b365);
   int n182=CopyBuffer(g_ind,BUF_MA182,0,totalBars,b182);
   int n121=CopyBuffer(g_ind,BUF_MA121,0,totalBars,b121);
   int n30=CopyBuffer(g_ind,BUF_MA30,0,totalBars,b30);
   int n14=CopyBuffer(g_ind,BUF_MA14,0,totalBars,b14);
   int n7=CopyBuffer(g_ind,BUF_MA7,0,totalBars,b7);
   int n3=CopyBuffer(g_ind,BUF_MA3,0,totalBars,b3);
   if(nM<maxBar) maxBar=nM; if(n365<maxBar) maxBar=n365;
   if(n182<maxBar) maxBar=n182; if(n121<maxBar) maxBar=n121;
   if(n30<maxBar) maxBar=n30; if(n14<maxBar) maxBar=n14;
   if(n7<maxBar) maxBar=n7; if(n3<maxBar) maxBar=n3;

   if(maxBar<10) return false;

   // Ridimensiona tutti gli array a maxBar
   ArrayResize(o,maxBar); ArrayResize(h,maxBar); ArrayResize(l,maxBar);
   ArrayResize(c,maxBar); ArrayResize(t,maxBar);
   ArrayResize(bM,maxBar); ArrayResize(b365,maxBar);
   ArrayResize(b182,maxBar); ArrayResize(b121,maxBar);
   ArrayResize(b30,maxBar); ArrayResize(b14,maxBar);
   ArrayResize(b7,maxBar); ArrayResize(b3,maxBar);
   return true;
}

//+------------------------------------------------------------------+
int OnInit()
{
   g_ind = iCustom(_Symbol,_Period,InpIndicatorName);
   if(g_ind==INVALID_HANDLE) { Print("iCustom fallito"); return INIT_FAILED; }

   for(int i=0;i<7;i++)
   {
      g_hMA[i] = iMA(_Symbol,ANCHOR_TF,TimeToBars(g_per[i]),0,MODE_SMA,PRICE_CLOSE);
      if(g_hMA[i]==INVALID_HANDLE) { Print("MA",g_per[i]," fallito"); return INIT_FAILED; }
   }

   g_startTime = StringToTime(InpStartDate);
   g_endTime   = StringToTime(InpEndDate)+86399;
   Print(StringFormat("Export PAPP | %s -> %s | file=%s | chart bars=%d | D1 bars=%d",
       TimeToString(g_startTime),TimeToString(g_endTime),InpFileName,
       Bars(_Symbol,_Period),Bars(_Symbol,ANCHOR_TF)));
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int)
{
   if(g_ind!=INVALID_HANDLE) IndicatorRelease(g_ind);
   for(int i=0;i<7;i++) if(g_hMA[i]!=INVALID_HANDLE) IndicatorRelease(g_hMA[i]);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(g_done) return;
   g_done = true;

   double dummy;
   if(!ReadBuf(BUF_MEDIAN,1,dummy))
   {
      Comment("Export_PAPP: attendo l'indicatore...");
      g_done=false; return;
   }

   int totalBars = Bars(_Symbol,_Period);
   if(totalBars<10) { Print("Poche barre"); return; }

   // Precarica OHLC + indicator buffers (serve maxBar prima di sStart/sEnd clamp)
   double o[],h[],l[],c[]; datetime t[];
   double bM[],b365[],b182[],b121[],b30[],b14[],b7[],b3[];
   if(!LoadBuffers(o,h,l,c,t,bM,b365,b182,b121,b30,b14,b7,b3,totalBars))
      { Print("ERRORE caricamento buffer"); return; }

   // Precarica D1: MA values su tutte le barre D1 disponibili
   int d1Bars = Bars(_Symbol,ANCHOR_TF);
   double d1MA[][7];
   bool d1ok=false;
   if(d1Bars>=10)
   {
      ArrayResize(d1MA,d1Bars);
      for(int m=0;m<7;m++)
      {
         double tmp[]; ArraySetAsSeries(tmp,true);
         int got = CopyBuffer(g_hMA[m],0,0,d1Bars,tmp);
         for(int s=0;s<got && s<d1Bars;s++) d1MA[s][m] = IsPriceOk(tmp[s])?tmp[s]:0.0;
      }
      d1ok=true;
   }
   else Print("Poche barre D1 (",d1Bars,") — metriche D1 saltate");

   int sStart = iBarShift(_Symbol,_Period,g_startTime,false);
   int sEnd   = iBarShift(_Symbol,_Period,g_endTime,false);
   if(sStart<0 || sStart>=ArraySize(c)) sStart=ArraySize(c)-1;
   if(sEnd<0) sEnd=0;
   if(sStart<=sEnd) { Print("Range date vuoto"); return; }

   Print(StringFormat("Barre: %d (shift %d->%d) su %d",sStart-sEnd+1,sStart,sEnd,ArraySize(c)));

   // Apri CSV
   int fh = FileOpen(InpFileName,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fh==INVALID_HANDLE) { Print("ERRORE file: ",GetLastError()); return; }

   FileWrite(fh,
       "datetime","open","high","low","close",
       "median","MA365","MA182","MA121","MA30","MA14","MA7","MA3",
       "dMed%","d365%","d182%","d121%","d30%","d14%","d7%","d3%",
       "a365","a182","a121","a30","a14","a7","a3","aMed",
       "fastAvg","slowAvg","spread","spreadVel",
       "orderScore","s14_30","s7_30",
       "longBelow","longAbove",
       "cluster%","vel%","acc%","vol%",
       "crossMed","crossMA3",
       "MA3_7","MA7_14","MA14_30","MA30_121","MA121_182","MA182_365");

   int written=0, total = sStart-sEnd+1;
   Comment(StringFormat("Export PAPP: 0/%d barre...",total));
   for(int s=sStart;s>=sEnd;s--)
   {
       if(!IsPriceOk(bM[s]) || !IsPriceOk(c[s])) continue;
       if((written%5000)==0) Comment(StringFormat("Export PAPP: %d/%d barre...",written,total));

      double med=bM[s], v365=b365[s], v182=b182[s], v121=b121[s];
      double v30=b30[s], v14=b14[s], v7=b7[s], v3=b3[s];
      double cls=c[s];

      // Distanze %
      double dMed = med>0?(cls-med)/med*100.0:0;
      double d365 = v365>0?(cls-v365)/v365*100.0:0;
      double d182 = v182>0?(cls-v182)/v182*100.0:0;
      double d121 = v121>0?(cls-v121)/v121*100.0:0;
      double d30  = v30>0?(cls-v30)/v30*100.0:0;
      double d14  = v14>0?(cls-v14)/v14*100.0:0;
      double d7   = v7>0?(cls-v7)/v7*100.0:0;
      double d3   = v3>0?(cls-v3)/v3*100.0:0;

      // Flag sopra=1 sotto=0
      int aMed=cls>med?1:0, a365=cls>v365?1:0, a182=cls>v182?1:0, a121=cls>v121?1:0;
      int a30=cls>v30?1:0, a14=cls>v14?1:0, a7=cls>v7?1:0, a3=cls>v3?1:0;

      // Frattale
      double fastAvg=(v3+v7+v14)/3.0, slowAvg=(v121+v182+v365)/3.0;
      double spreadF=fastAvg-slowAvg;
      double spreadVel=0;
      int nBars=ArraySize(c);
      if(s+1<nBars && IsPriceOk(bM[s+1]))
      {
         double f2=(b3[s+1]+b7[s+1]+b14[s+1])/3.0;
         double s2=(b121[s+1]+b182[s+1]+b365[s+1])/3.0;
         spreadVel=spreadF-(f2-s2);
      }

      // Order score
      int os=0;
      if(IsPriceOk(v3)&&IsPriceOk(v7)) os+=(v3>v7)?1:-1;
      if(IsPriceOk(v7)&&IsPriceOk(v14)) os+=(v7>v14)?1:-1;
      if(IsPriceOk(v14)&&IsPriceOk(v30)) os+=(v14>v30)?1:-1;
      if(IsPriceOk(v30)&&IsPriceOk(v121)) os+=(v30>v121)?1:-1;
      if(IsPriceOk(v121)&&IsPriceOk(v182)) os+=(v121>v182)?1:-1;
      if(IsPriceOk(v182)&&IsPriceOk(v365)) os+=(v182>v365)?1:-1;

      int s14_30=(v14>v30)?1:0, s7_30=(v7>v30)?1:0;
      int longBelow=(v365<med&&v182<med&&v121<med)?1:0;
      int longAbove=(v365>med&&v182>med&&v121>med)?1:0;

      // Incroci close
      int crossMed=0, crossMA3=0;
      if(s+1<ArraySize(c) && IsPriceOk(bM[s+1]) && IsPriceOk(c[s+1]))
      {
         double cp=c[s+1];
         if((cls>med&&cp<=med)||(cls<med&&cp>=med)) crossMed=1;
         if((cls>v3&&cp<=v3)||(cls<v3&&cp>=v3)) crossMA3=1;
      }

      // Metriche D1: cluster, vel, acc, vol
      double clu=0,vel=0,acc=0,vol=0;
      int d1Idx = iBarShift(_Symbol,ANCHOR_TF,t[s],false);
      if(d1ok && d1Idx>=0 && d1Idx+CLWIN+KSLOPE+NVOL<d1Bars)
      {
         // Cluster
         double ca[252]; int cc=0;
         for(int j=d1Idx;j<d1Idx+CLWIN && j<d1Bars;j++)
         {
            double vv[7]; int cv=0;
            for(int m=0;m<7;m++) { double x=d1MA[j][m]; if(IsPriceOk(x)) vv[cv++]=x; }
            if(cv>=2)
            {
               double md=MedArr(vv,cv);
               if(md>0) { double ds=0; for(int n=0;n<cv;n++) ds+=MathAbs(vv[n]-md)/md*100.0; if(cc<252) ca[cc++]=ds/cv; }
            }
         }
         if(cc>0) clu=ca[0];

         // Velocita'
         double v7b[7]; int v7c=0;
         for(int m=0;m<7;m++)
         {
            double a=d1MA[d1Idx][m], b=d1MA[d1Idx+KSLOPE][m];
            if(IsPriceOk(a)&&IsPriceOk(b)&&b>0) v7b[v7c++]=(a-b)/b*100.0;
         }
         if(v7c>0) vel=MathAbs(MedArr(v7b,v7c));

         // Accelerazione
         v7c=0;
         for(int m=0;m<7;m++)
         {
            double a=d1MA[d1Idx][m], b=d1MA[d1Idx+KSLOPE][m], d=d1MA[d1Idx+2*KSLOPE][m];
            if(IsPriceOk(a)&&IsPriceOk(b)&&IsPriceOk(d)&&d>0) v7b[v7c++]=(a-2.0*b+d)/d*100.0;
         }
         if(v7c>0) acc=MathAbs(MedArr(v7b,v7c));

         // Volatilita'
         v7c=0;
         for(int m=0;m<7;m++)
         {
            double rr[NVOL]; int rc=0;
            for(int t2=d1Idx;t2<d1Idx+NVOL && t2+1<d1Bars;t2++)
            {
               double a=d1MA[t2][m], b2=d1MA[t2+1][m];
               if(IsPriceOk(a)&&IsPriceOk(b2)&&b2>0) rr[rc++]=(a-b2)/b2*100.0;
            }
            if(rc>=2)
            {
               double mn=0; for(int q=0;q<rc;q++) mn+=rr[q]; mn/=rc;
               double s2=0; for(int q=0;q<rc;q++) { double dd=rr[q]-mn; s2+=dd*dd; }
               v7b[v7c++]=MathSqrt(s2/(rc-1));
            }
         }
         if(v7c>0) vol=MedArr(v7b,v7c);
      }

      FileWrite(fh,
          TimeToString(t[s]),
          DoubleToString(o[s],_Digits),DoubleToString(h[s],_Digits),
          DoubleToString(l[s],_Digits),DoubleToString(cls,_Digits),
          DoubleToString(med,_Digits),DoubleToString(v365,_Digits),
          DoubleToString(v182,_Digits),DoubleToString(v121,_Digits),
          DoubleToString(v30,_Digits),DoubleToString(v14,_Digits),
          DoubleToString(v7,_Digits),DoubleToString(v3,_Digits),
          DoubleToString(dMed,4),DoubleToString(d365,4),DoubleToString(d182,4),
          DoubleToString(d121,4),DoubleToString(d30,4),DoubleToString(d14,4),
          DoubleToString(d7,4),DoubleToString(d3,4),
          a365,a182,a121,a30,a14,a7,a3,aMed,
          DoubleToString(fastAvg,_Digits),DoubleToString(slowAvg,_Digits),
          DoubleToString(spreadF,6),DoubleToString(spreadVel,6),
          os,s14_30,s7_30,
          longBelow,longAbove,
          DoubleToString(clu,4),DoubleToString(vel,4),
          DoubleToString(acc,4),DoubleToString(vol,4),
          crossMed,crossMA3,
          v3>v7?1:0, v7>v14?1:0, v14>v30?1:0,
          v30>v121?1:0, v121>v182?1:0, v182>v365?1:0);

      written++;
   }

   FileClose(fh);
   Comment(StringFormat("EXPORT COMPLETATO: %s | %d righe",InpFileName,written));
   Print(StringFormat(">>> EXPORT COMPLETATO: %s | %d righe",InpFileName,written));
}
//+------------------------------------------------------------------+
