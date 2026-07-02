//+------------------------------------------------------------------+
//|                                                   Export_PAPP.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
#property copyright "PHAI v2"
#property version   "2.05"
#property description "Esporta D1-anchor MA + tutte le metriche PaPP in CSV"
#property description "v2.05: attesa readiness robusta (barre stabili + indicatore calc.)"
#property description "Crossover calcolati su D1 reali, non su valori interpolati"
#property description "v2.04: sorgente UNICA = buffer iCustom. Crossover/cluster/vel/acc/vol"
#property description "       derivati dalle stesse MA scritte nelle colonne (no iMA paralleli)."
#property script_show_inputs

input string InpIndicatorName = "PHAI_Median.ex5";
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

//+------------------------------------------------------------------+
bool IsPriceOk(double v) { return (v>0.0 && v<1.0e12); }

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
// Percentile di 'cur' nell'array (frazione di valori <= cur). Allineato
// all'indicatore (PctlOf): per vel/acc va passato |cur| (array in magnitudine).
double PctlOf(double &arr[],int cc,double cur)
{
   if(cc<=0) return 0.5;
   int b=0; for(int k=0;k<cc;k++) if(arr[k]<=cur) b++;
   return (double)b/cc;
}

//+------------------------------------------------------------------+
void OnStart()
{
   // IMPORTANTE: stessi parametri dell'EA (EA_Pattern OnInit) per ottenere
   // valori MA IDENTICI. Mapping input PHAI_Median:
   //   FontSize=9, Smooth=false, ShowMA=true, ShowPanel=true, PanelBg, InpSignals=true
   // Smooth=false / InpSignals=true => valori RAW a gradino (no interpolazione,
   // no look-ahead) coerenti su qualunque timeframe, identici a quelli usati dall'EA.
   int g_ind = iCustom(_Symbol,_Period,InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_ind==INVALID_HANDLE) { Print("ERRORE: iCustom fallito"); return; }

   // Attesa robusta: l'indicatore dev'essere calcolato su TUTTE le barre del
   // grafico E il numero di barre deve essersi stabilizzato (la history del broker
   // puo' ancora scaricarsi in background e allungare il grafico). Il vecchio check
   // ">10" passava subito -> CopyBuffer restituiva EMPTY_VALUE sulle barre non ancora
   // calcolate -> export a 0 righe. Ora aspettiamo readiness reale.
   int prevBars=-1, stable=0;
   bool ready=false;
   for(int att=0; att<600; att++)               // fino a ~60s
   {
      int nb = Bars(_Symbol,_Period);
      int bc = BarsCalculated(g_ind);
      if(nb==prevBars) stable++; else stable=0;  // conteggio barre invariato?
      prevBars = nb;
      // pronto quando: barre stabili da >=5 cicli, indicatore calcolato su tutte le barre
      if(nb>365 && bc>=nb && stable>=5) { ready=true; break; }
      Sleep(100);
   }
   if(!ready)
   {
      Print(StringFormat("ERRORE: indicatore non pronto (bars=%d, calcolate=%d) - riprova quando la history e' caricata",
            Bars(_Symbol,_Period), BarsCalculated(g_ind)));
      IndicatorRelease(g_ind); return;
   }

   datetime g_startTime = StringToTime(InpStartDate);
   datetime g_endTime   = StringToTime(InpEndDate)+86399;

   Print(StringFormat("Export PAPP v2.04 | %s -> %s | file=%s | chart bars=%d | D1 bars=%d",
       TimeToString(g_startTime),TimeToString(g_endTime),InpFileName,
       Bars(_Symbol,_Period),Bars(_Symbol,ANCHOR_TF)));

   int totalBars = Bars(_Symbol,_Period);
   if(totalBars<10) { Print("Poche barre"); IndicatorRelease(g_ind); return; }

   double o[],h[],l[],c[]; datetime t[];
   double bM[],b365[],b182[],b121[],b30[],b14[],b7[],b3[];
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

   if(maxBar<10) { Print("ERRORE: pochi dati caricati"); IndicatorRelease(g_ind); return; }

   ArrayResize(o,maxBar); ArrayResize(h,maxBar); ArrayResize(l,maxBar);
   ArrayResize(c,maxBar); ArrayResize(t,maxBar);
   ArrayResize(bM,maxBar); ArrayResize(b365,maxBar);
   ArrayResize(b182,maxBar); ArrayResize(b121,maxBar);
   ArrayResize(b30,maxBar); ArrayResize(b14,maxBar);
   ArrayResize(b7,maxBar); ArrayResize(b3,maxBar);

   // --- Precarica D1: MA values, close, e median ---
   // SORGENTE UNICA: le MA D1 usate per crossover/cluster/vel/acc/vol vengono
   // CAMPIONATE dagli stessi buffer iCustom (b365..b3) scritti nelle colonne CSV,
   // NON da handle iMA paralleli. Cosi' i crossMAxxx sono per costruzione coerenti
   // con le colonne MAxxx, anche se i periodi MA dell'indicatore cambiano.
   // I valori "raw step" sono costanti entro la stessa barra D1, quindi campionare
   // una qualunque barra-chart appartenente alla D1 restituisce il valore D1 esatto.
   int d1Bars = Bars(_Symbol,ANCHOR_TF);
   double d1MA[][7];
   double d1Close[];
   double d1Median[];
   bool d1ok=false;
   if(d1Bars>=10)
   {
      ArrayResize(d1MA,d1Bars);
      ArrayResize(d1Median,d1Bars);
      // Carica D1 close (chiusura D1 reale, per il confronto crossover)
      ArraySetAsSeries(d1Close,true);
      int nD1C = CopyClose(_Symbol,ANCHOR_TF,0,d1Bars,d1Close);
      if(nD1C>0) d1Bars = MathMin(d1Bars,nD1C);

      int nbarsChart = ArraySize(c);
      for(int db=0; db<d1Bars; db++)
      {
         datetime d1t = iTime(_Symbol,ANCHOR_TF,db);
         int cb = (d1t>0) ? iBarShift(_Symbol,_Period,d1t,false) : -1;
         // valido solo se la barra-chart appartiene a questa D1 (>= apertura D1)
         bool ok = (cb>=0 && cb<nbarsChart && t[cb]>=d1t);
         double v[7];
         for(int m=0;m<7;m++)
         {
            double x = 0.0;
            if(ok)
            {
               switch(m)
               {
                  case 0: x=b365[cb]; break;  case 1: x=b182[cb]; break;
                  case 2: x=b121[cb]; break;  case 3: x=b30[cb];  break;
                  case 4: x=b14[cb];  break;  case 5: x=b7[cb];   break;
                  case 6: x=b3[cb];   break;
               }
            }
            d1MA[db][m] = IsPriceOk(x)?x:0.0;
            v[m]=d1MA[db][m];
         }
         d1Median[db] = MedArr(v,7);
      }
      d1ok=true;
   }
   else Print("Poche barre D1 (",d1Bars,") — metriche D1 saltate");

   int sStart = iBarShift(_Symbol,_Period,g_startTime,false);
   int sEnd   = iBarShift(_Symbol,_Period,g_endTime,false);
   if(sStart<0 || sStart>=ArraySize(c)) sStart=ArraySize(c)-1;
   if(sEnd<0) sEnd=0;
   if(sStart<=sEnd) { Print("Range date vuoto"); IndicatorRelease(g_ind); return; }

   Print(StringFormat("Barre: %d (shift %d->%d) su %d",sStart-sEnd+1,sStart,sEnd,ArraySize(c)));

   int fh = FileOpen(InpFileName,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fh==INVALID_HANDLE) { Print("ERRORE file: ",GetLastError()); IndicatorRelease(g_ind); return; }

   FileWrite(fh,
       "datetime","open","high","low","close",
       "median","MA365","MA182","MA121","MA30","MA14","MA7","MA3",
       "dMed%","d365%","d182%","d121%","d30%","d14%","d7%","d3%",
       "a365","a182","a121","a30","a14","a7","a3","aMed",
       "fastAvg","slowAvg","spread","spreadVel",
       "orderScore","s14_30","s7_30",
       "longBelow","longAbove",
       "cluster%","vel%","acc%","vol%",
       "cluPct","velPct","accPct","volPct",
       "crossMA365","crossMA182","crossMA121","crossMA30","crossMA14","crossMA7","crossMA3","crossMed",
       "MA3_7","MA7_14","MA14_30","MA30_121","MA121_182","MA182_365");

   int written=0, total = sStart-sEnd+1;
   Comment(StringFormat("Export PAPP v2.04: 0/%d barre...",total));

   // --- Loop principale ---
   int prevD1Cur = -1;

   for(int s=sStart;s>=sEnd;s--)
   {
       if(!IsPriceOk(bM[s]) || !IsPriceOk(c[s])) continue;
       if((written%5000)==0) Comment(StringFormat("Export PAPP v2.04: %d/%d barre...",written,total));

      double med=bM[s], v365=b365[s], v182=b182[s], v121=b121[s];
      double v30=b30[s], v14=b14[s], v7=b7[s], v3=b3[s];
      double cls=c[s];

      double dMed = med>0?(cls-med)/med*100.0:0;
      double d365 = v365>0?(cls-v365)/v365*100.0:0;
      double d182 = v182>0?(cls-v182)/v182*100.0:0;
      double d121 = v121>0?(cls-v121)/v121*100.0:0;
      double d30  = v30>0?(cls-v30)/v30*100.0:0;
      double d14  = v14>0?(cls-v14)/v14*100.0:0;
      double d7   = v7>0?(cls-v7)/v7*100.0:0;
      double d3   = v3>0?(cls-v3)/v3*100.0:0;

      int aMed=cls>med?1:0, a365=cls>v365?1:0, a182=cls>v182?1:0, a121=cls>v121?1:0;
      int a30=cls>v30?1:0, a14=cls>v14?1:0, a7=cls>v7?1:0, a3=cls>v3?1:0;

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

      // --- CROSSOVER su D1 REALI (solo su prima barra di ogni nuova D1) ---
      // Confronta D1 close vs D1 MA/Median a barre D1 consecutive
      int crossMA365=0, crossMA182=0, crossMA121=0, crossMA30=0;
      int crossMA14=0, crossMA7=0, crossMA3=0, crossMed=0;

      int d1Cur = iBarShift(_Symbol,ANCHOR_TF,t[s],false);

      if(d1ok && d1Cur>0 && d1Cur != prevD1Cur && prevD1Cur>=0)
      {
         // d1Cur + 1 = barra D1 precedente (indice piu' alto = piu' vecchia)
         // d1Cur = barra D1 corrente (indice piu' basso = piu' recente)
         // Bullish: close[prec] <= MA[prec], close[cur] > MA[cur]
         // Bearish: close[prec] >= MA[prec], close[cur] < MA[cur]
         int prevIdx = d1Cur + 1;
         if(prevIdx < d1Bars)
         {
            double d1cCur = d1Close[d1Cur];
            double d1cPrev = d1Close[prevIdx];

            for(int m=0; m<7; m++)
            {
               double maCur = d1MA[d1Cur][m];
               double maPrev = d1MA[prevIdx][m];
               if(!IsPriceOk(maCur) || !IsPriceOk(maPrev)) continue;
               int cross = 0;
               if(d1cCur > maCur && d1cPrev <= maPrev) cross = 1;
               else if(d1cCur < maCur && d1cPrev >= maPrev) cross = -1;
               // Assegna al cross corrispondente
               switch(m)
               {
                  case 0: crossMA365 = cross; break;
                  case 1: crossMA182 = cross; break;
                  case 2: crossMA121 = cross; break;
                  case 3: crossMA30  = cross; break;
                  case 4: crossMA14  = cross; break;
                  case 5: crossMA7   = cross; break;
                  case 6: crossMA3   = cross; break;
               }
            }
            // Median
            double medCur = d1Median[d1Cur];
            double medPrev = d1Median[prevIdx];
            if(IsPriceOk(medCur) && IsPriceOk(medPrev))
            {
               if(d1cCur > medCur && d1cPrev <= medPrev) crossMed = 1;
               else if(d1cCur < medCur && d1cPrev >= medPrev) crossMed = -1;
            }
         }
      }
      prevD1Cur = d1Cur;

      // Metriche D1: cluster, vel, acc, vol = valore della barra CORRENTE
      // + percentile sulla finestra CLWIN (252 barre D1). Coerente con l'indicatore:
      // il valore e' quello di oggi, la finestra serve al percentile (non a fare media).
      double clu=0,vel=0,acc=0,vol=0;
      double cluP=0.5,velP=0.5,accP=0.5,volP=0.5;
      int d1Idx = iBarShift(_Symbol,ANCHOR_TF,t[s],false);
      if(d1ok && d1Idx>=0 && d1Idx+CLWIN+KSLOPE+NVOL<d1Bars)
      {
         double caA[252], veA[252], acA[252], voA[252];   // finestre: cluster, |vel|, |acc|, vol
         int caC=0, veC=0, acC=0, voC=0;
         for(int j=d1Idx;j<d1Idx+CLWIN && j<d1Bars;j++)
         {
            double v7b[7]; int v7c;
            // --- Cluster alla barra j ---
            double vv[7]; int cv=0;
            for(int m=0;m<7;m++) { double x=d1MA[j][m]; if(IsPriceOk(x)) vv[cv++]=x; }
            if(cv>=2)
            {
               double md=MedArr(vv,cv);
               if(md>0)
               {
                  double ds=0; for(int n=0;n<cv;n++) ds+=MathAbs(vv[n]-md)/md*100.0;
                  double cval=ds/cv;
                  if(caC<252) caA[caC++]=cval;
                  if(j==d1Idx) clu=cval;          // barra corrente
               }
            }
            // --- Velocity alla barra j ---
            v7c=0;
            for(int m=0;m<7;m++) { double a=d1MA[j][m], b=d1MA[j+KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&b>0) v7b[v7c++]=(a-b)/b*100.0; }
            if(v7c>0) { double vv2=MedArr(v7b,v7c); if(veC<252) veA[veC++]=MathAbs(vv2); if(j==d1Idx) vel=vv2; }
            // --- Acceleration alla barra j ---
            v7c=0;
            for(int m=0;m<7;m++) { double a=d1MA[j][m], b=d1MA[j+KSLOPE][m], d=d1MA[j+2*KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&IsPriceOk(d)&&d>0) v7b[v7c++]=(a-2.0*b+d)/d*100.0; }
            if(v7c>0) { double av2=MedArr(v7b,v7c); if(acC<252) acA[acC++]=MathAbs(av2); if(j==d1Idx) acc=av2; }
            // --- Volatility alla barra j ---
            v7c=0;
            for(int m=0;m<7;m++)
            {
               double rr[NVOL]; int rc=0;
               for(int t2=j;t2<j+NVOL && t2+1<d1Bars;t2++) { double a=d1MA[t2][m], b2=d1MA[t2+1][m]; if(IsPriceOk(a)&&IsPriceOk(b2)&&b2>0) rr[rc++]=(a-b2)/b2*100.0; }
               if(rc>=2) { double mn=0; for(int q=0;q<rc;q++) mn+=rr[q]; mn/=rc; double s2=0; for(int q=0;q<rc;q++) { double dd=rr[q]-mn; s2+=dd*dd; } v7b[v7c++]=MathSqrt(s2/(rc-1)); }
            }
            if(v7c>0) { double ov2=MedArr(v7b,v7c); if(voC<252) voA[voC++]=ov2; if(j==d1Idx) vol=ov2; }
         }
         // Percentili: vel/acc sulla MAGNITUDINE (come l'indicatore), cluster/vol sul valore.
         cluP=PctlOf(caA,caC,clu);
         velP=PctlOf(veA,veC,MathAbs(vel));
         accP=PctlOf(acA,acC,MathAbs(acc));
         volP=PctlOf(voA,voC,vol);
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
          DoubleToString(cluP,3),DoubleToString(velP,3),
          DoubleToString(accP,3),DoubleToString(volP,3),
          crossMA365,crossMA182,crossMA121,crossMA30,
          crossMA14,crossMA7,crossMA3,crossMed,
          v3>v7?1:0, v7>v14?1:0, v14>v30?1:0,
          v30>v121?1:0, v121>v182?1:0, v182>v365?1:0);

      written++;
   }

   FileClose(fh);
   Comment(StringFormat("EXPORT COMPLETATO: %s | %d righe",InpFileName,written));
   Print(StringFormat(">>> EXPORT COMPLETATO v2.04: %s | %d righe",InpFileName,written));

   IndicatorRelease(g_ind);
  
}
//+------------------------------------------------------------------+
