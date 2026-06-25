//+------------------------------------------------------------------+
//|                                                 Export_Events.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
//| Esporta due tabelle EVENT-BASED per il pattern mining:           |
//|                                                                  |
//|  1) STATE_D1_<SYM>.csv  (1 riga per barra D1)                     |
//|     - 8 livelli (7 MA + mediana) raw-step                        |
//|     - ranking completo (chi sta sopra chi)                       |
//|     - 28 bit di posizione p<A>_<B> (1 = A>B)                      |
//|     - 28 eventi di incrocio linea-linea x<A>_<B>                  |
//|       (+1 = A ha incrociato B verso l'alto oggi, -1 = verso il   |
//|        basso, 0 = nessun incrocio)                               |
//|     - metriche: spread/spreadVel/cluster/vel/acc/vol             |
//|                                                                  |
//|  2) PRICECROSS_<SYM>.csv  (1 riga per ogni incrocio prezzo-linea)|
//|     rilevato su barre M1 (close-to-close, baseline resettata     |
//|     a ogni nuova D1 cosi' lo "scalino" delle linee NON genera    |
//|     falsi incroci). Ogni evento porta il contesto del giorno.    |
//|                                                                  |
//| I livelli sono letti da iCustom su D1 (Smooth=false/InpSignals=  |
//| true => raw step), quindi 1 valore esatto per giorno. Le M1      |
//| servono solo per i prezzi. Esegui lo script su QUALSIASI grafico |
//| del simbolo voluto.                                              |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Esporta STATE_D1 (geometria+incroci linea-linea) e PRICECROSS (incroci prezzo-linea su M1)"
#property script_show_inputs

input string InpIndicatorName = "PaPP_Median.ex5";
input string InpStartDate     = "2024.01.01";
input string InpEndDate       = "2026.06.20";
input int    InpH1            = 60;     // orizzonte forward 1 (minuti, 0=off)
input int    InpH2            = 240;    // orizzonte forward 2 (minuti, 0=off)
input int    InpH3            = 1440;   // orizzonte forward 3 (minuti, 0=off)

#define ANCHOR_TF PERIOD_D1
#define KSLOPE 5
#define NVOL   14
#define CLWIN  252
#define NLEV   8     // 7 MA + mediana

// Mapping buffer iCustom: 0=median,1=MA365,2=MA182,3=MA121,4=MA30,5=MA14,6=MA7,7=MA3
// Ordine interno dei livelli (lev[0..7]):
//   0=MA365 1=MA182 2=MA121 3=MA30 4=MA14 5=MA7 6=MA3 7=MED
int    gBuf[NLEV] = {1,2,3,4,5,6,7,0};
string gLab[NLEV] = {"365","182","121","30","14","7","3","M"};

// dati per-D1 (series: indice 0 = piu' recente)
double  g_lev[][NLEV];
int     g_d1Bars = 0;

// contesto per-D1 precalcolato (per le righe PRICECROSS), dimensione = g_d1Bars
string  g_rank[];
double  g_spread[], g_spreadVel[], g_clu[], g_vel[], g_acc[], g_vol[];
bool    g_ctxOk[];

//+------------------------------------------------------------------+
bool IsPriceOk(double v) { return (v>0.0 && v<1.0e12); }
int  Sgn(double a,double b){ return (a>b)?1:((a<b)?-1:0); }

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
// Metriche giornaliere (cluster/vel/acc/vol/spread) su finestra CLWIN.
// Indici MA in g_lev: 0..6 = MA365,182,121,30,14,7,3
void DailyMetrics(int db,double &spread,double &spreadVel,
                  double &clu,double &vel,double &acc,double &vol)
{
   spread=0; spreadVel=0; clu=0; vel=0; acc=0; vol=0;
   // spread frattale: squadra veloce (MA3,7,14 = idx 6,5,4) - squadra lenta (MA365,182,121 = idx 0,1,2)
   double f=(g_lev[db][6]+g_lev[db][5]+g_lev[db][4])/3.0;
   double s=(g_lev[db][0]+g_lev[db][1]+g_lev[db][2])/3.0;
   spread=f-s;
   if(db+1<g_d1Bars)
   {
      double fy=(g_lev[db+1][6]+g_lev[db+1][5]+g_lev[db+1][4])/3.0;
      double sy=(g_lev[db+1][0]+g_lev[db+1][1]+g_lev[db+1][2])/3.0;
      spreadVel=spread-(fy-sy);
   }
   if(db+CLWIN+2*KSLOPE+NVOL>=g_d1Bars) return;   // storia insufficiente per le metriche di finestra

   // cluster: dispersione media delle MA sulla finestra CLWIN
   double sm=0; int cc=0;
   for(int j=db;j<db+CLWIN;j++)
   {
      double vv[7]; int cv=0;
      for(int m=0;m<7;m++){ double x=g_lev[j][m]; if(IsPriceOk(x)) vv[cv++]=x; }
      if(cv>=2){ double md=MedArr(vv,cv); if(md>0){ double ds=0; for(int n=0;n<cv;n++) ds+=MathAbs(vv[n]-md)/md*100.0; sm+=ds/cv; cc++; } }
   }
   if(cc>0) clu=sm/cc;

   // velocity
   double v7[7]; int vc=0;
   for(int m=0;m<7;m++){ double a=g_lev[db][m],b=g_lev[db+KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&b>0) v7[vc++]=(a-b)/b*100.0; }
   if(vc>0) vel=MathAbs(MedArr(v7,vc));
   // acceleration
   vc=0;
   for(int m=0;m<7;m++){ double a=g_lev[db][m],b=g_lev[db+KSLOPE][m],d=g_lev[db+2*KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&IsPriceOk(d)&&d>0) v7[vc++]=(a-2.0*b+d)/d*100.0; }
   if(vc>0) acc=MathAbs(MedArr(v7,vc));
   // volatility
   vc=0;
   for(int m=0;m<7;m++)
   {
      double rr[NVOL]; int rc=0;
      for(int t2=db;t2<db+NVOL && t2+1<g_d1Bars;t2++){ double a=g_lev[t2][m],b2=g_lev[t2+1][m]; if(IsPriceOk(a)&&IsPriceOk(b2)&&b2>0) rr[rc++]=(a-b2)/b2*100.0; }
      if(rc>=2){ double mn=0; for(int q=0;q<rc;q++) mn+=rr[q]; mn/=rc; double s2=0; for(int q=0;q<rc;q++){ double dd=rr[q]-mn; s2+=dd*dd; } v7[vc++]=MathSqrt(s2/(rc-1)); }
   }
   if(vc>0) vol=MedArr(v7,vc);
}

//+------------------------------------------------------------------+
// Ranking discendente dei livelli validi -> "365>M>121>..."
string RankStr(int db)
{
   int idx[NLEV]; double val[NLEV]; int c=0;
   for(int k=0;k<NLEV;k++){ if(IsPriceOk(g_lev[db][k])){ idx[c]=k; val[c]=g_lev[db][k]; c++; } }
   for(int a=0;a<c;a++) for(int b=a+1;b<c;b++) if(val[b]>val[a]){ double tv=val[a]; val[a]=val[b]; val[b]=tv; int ti=idx[a]; idx[a]=idx[b]; idx[b]=ti; }
   string r="";
   for(int a=0;a<c;a++){ r+=gLab[idx[a]]; if(a<c-1) r+=">"; }
   return r;
}

//+------------------------------------------------------------------+
// Escursione forward dal bar i: per ogni orizzonte H[q] (minuti) calcola
//   up[q]  = massimo movimento al rialzo   (maxHigh-cl)/cl*100   (>=0)
//   dn[q]  = massimo movimento al ribasso  (cl-minLow)/cl*100    (>=0)
//   ret[q] = ritorno close-to-close        (closeFine-cl)/cl*100 (segno)
// Un solo scan in avanti; H[] deve essere ordinato crescente.
// Se i dati finiscono prima di H[q], usa quanto raccolto (finestra troncata).
void ForwardExc(const MqlRates &r[],int n,int i,double cl,
                const int &H[],int nH,double &up[],double &dn[],double &ret[])
{
   for(int q=0;q<nH;q++){ up[q]=0; dn[q]=0; ret[q]=0; }
   if(cl<=0) return;
   datetime t0=r[i].time;
   double maxHi=cl, minLo=cl, lastClose=cl;
   int hi=0;
   for(int j=i+1;j<n && hi<nH;j++)
   {
      long dtmin=(long)(r[j].time-t0)/60;
      while(hi<nH && dtmin>H[hi])
      {
         up[hi]=(maxHi-cl)/cl*100.0;
         dn[hi]=(cl-minLo)/cl*100.0;
         ret[hi]=(lastClose-cl)/cl*100.0;
         hi++;
      }
      if(hi>=nH) break;
      if(r[j].high>maxHi) maxHi=r[j].high;
      if(r[j].low <minLo) minLo=r[j].low;
      lastClose=r[j].close;
   }
   while(hi<nH)   // dati esauriti: chiudi gli orizzonti rimasti con la finestra disponibile
   {
      up[hi]=(maxHi-cl)/cl*100.0;
      dn[hi]=(cl-minLo)/cl*100.0;
      ret[hi]=(lastClose-cl)/cl*100.0;
      hi++;
   }
}

//+------------------------------------------------------------------+
void OnStart()
{
   // iCustom su D1, stessi parametri di Export_PAPP => valori raw-step coerenti con l'EA
   int g_ind = iCustom(_Symbol,ANCHOR_TF,InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(g_ind==INVALID_HANDLE){ Print("ERRORE: iCustom fallito"); return; }
   for(int att=0; att<100; att++){ if(BarsCalculated(g_ind)>10) break; Sleep(100); }
   if(BarsCalculated(g_ind)<=10){ Print("ERRORE: indicatore non pronto"); IndicatorRelease(g_ind); return; }

   datetime g_startTime = StringToTime(InpStartDate);
   datetime g_endTime   = StringToTime(InpEndDate)+86399;

   g_d1Bars = Bars(_Symbol,ANCHOR_TF);
   if(g_d1Bars<CLWIN+2*KSLOPE+NVOL+2){ Print("ERRORE: poche barre D1 (",g_d1Bars,")"); IndicatorRelease(g_ind); return; }

   // --- carica gli 8 livelli per ogni barra D1 (series, 0=recente) ---
   ArrayResize(g_lev,g_d1Bars);
   for(int k=0;k<NLEV;k++)
   {
      double tmp[]; ArraySetAsSeries(tmp,true);
      int got = CopyBuffer(g_ind,gBuf[k],0,g_d1Bars,tmp);
      if(got<=0){ Print("ERRORE CopyBuffer buf=",gBuf[k]," err=",GetLastError()); IndicatorRelease(g_ind); return; }
      for(int s=0;s<g_d1Bars;s++) g_lev[s][k] = (s<got && IsPriceOk(tmp[s])) ? tmp[s] : 0.0;
   }

   // --- precalcola contesto per-D1 (serve a PRICECROSS) ---
   ArrayResize(g_rank,g_d1Bars);   ArrayResize(g_ctxOk,g_d1Bars);
   ArrayResize(g_spread,g_d1Bars); ArrayResize(g_spreadVel,g_d1Bars);
   ArrayResize(g_clu,g_d1Bars);    ArrayResize(g_vel,g_d1Bars);
   ArrayResize(g_acc,g_d1Bars);    ArrayResize(g_vol,g_d1Bars);
   for(int db=0; db<g_d1Bars; db++)
   {
      DailyMetrics(db,g_spread[db],g_spreadVel[db],g_clu[db],g_vel[db],g_acc[db],g_vol[db]);
      g_rank[db]  = RankStr(db);
      g_ctxOk[db] = true;
   }

   // --- tempi D1 in ordine ASCENDENTE per il mapping veloce M1->D1 ---
   // ascT[a] = apertura della a-esima barra D1 (a=0 piu' vecchia).
   // indice series corrispondente = g_d1Bars-1-a
   datetime ascT[]; ArrayResize(ascT,g_d1Bars);
   for(int a=0;a<g_d1Bars;a++) ascT[a]=iTime(_Symbol,ANCHOR_TF,g_d1Bars-1-a);

   int dbStart = iBarShift(_Symbol,ANCHOR_TF,g_startTime,false);
   int dbEnd   = iBarShift(_Symbol,ANCHOR_TF,g_endTime,false);
   if(dbStart<0 || dbStart>=g_d1Bars) dbStart=g_d1Bars-1;
   if(dbEnd<0) dbEnd=0;
   if(dbStart<dbEnd){ Print("Range date vuoto"); IndicatorRelease(g_ind); return; }

   //================================================================
   // 1) STATE_D1 : geometria + incroci linea-linea (28 coppie)
   //================================================================
   string fState = StringFormat("STATE_D1_%s.csv",_Symbol);
   int fhS = FileOpen(fState,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fhS==INVALID_HANDLE){ Print("ERRORE file STATE: ",GetLastError()); IndicatorRelease(g_ind); return; }

   // header
   string hdr = "datetime";
   for(int k=0;k<NLEV;k++) hdr += ",L"+gLab[k];
   hdr += ",rank,spread,spreadVel,cluster,vel,acc,vol";
   for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++) hdr += ",p"+gLab[i]+"_"+gLab[j];
   for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++) hdr += ",x"+gLab[i]+"_"+gLab[j];
   FileWrite(fhS,hdr);

   int stateRows=0;
   for(int db=dbStart; db>=dbEnd; db--)   // cronologico: vecchio -> recente
   {
      datetime dt = iTime(_Symbol,ANCHOR_TF,db);
      string row = TimeToString(dt);
      for(int k=0;k<NLEV;k++) row += ","+DoubleToString(g_lev[db][k],_Digits);
      row += ","+g_rank[db];
      row += ","+DoubleToString(g_spread[db],6)+","+DoubleToString(g_spreadVel[db],6);
      row += ","+DoubleToString(g_clu[db],4)+","+DoubleToString(g_vel[db],4);
      row += ","+DoubleToString(g_acc[db],4)+","+DoubleToString(g_vol[db],4);
      // posizioni p<A>_<B> = 1 se A>B
      for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++)
      {
         int pv = (IsPriceOk(g_lev[db][i])&&IsPriceOk(g_lev[db][j])) ? (g_lev[db][i]>g_lev[db][j]?1:0) : 0;
         row += ","+IntegerToString(pv);
      }
      // incroci x<A>_<B>: confronto segno(A-B) oggi(db) vs ieri(db+1)
      for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++)
      {
         int cross=0;
         if(db+1<g_d1Bars && IsPriceOk(g_lev[db][i])&&IsPriceOk(g_lev[db][j])
            && IsPriceOk(g_lev[db+1][i])&&IsPriceOk(g_lev[db+1][j]))
         {
            int sc=Sgn(g_lev[db][i],g_lev[db][j]);
            int sp=Sgn(g_lev[db+1][i],g_lev[db+1][j]);
            if(sc>0 && sp<=0) cross=1;
            else if(sc<0 && sp>=0) cross=-1;
         }
         row += ","+IntegerToString(cross);
      }
      FileWrite(fhS,row);
      stateRows++;
   }
   FileClose(fhS);
   Print(StringFormat(">>> STATE_D1: %s | %d righe",fState,stateRows));

   //================================================================
   // 2) PRICECROSS : incroci prezzo-linea su M1 (chunk temporali)
   //================================================================
   string fPC = StringFormat("PRICECROSS_%s.csv",_Symbol);
   int fhP = FileOpen(fPC,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fhP==INVALID_HANDLE){ Print("ERRORE file PRICECROSS: ",GetLastError()); IndicatorRelease(g_ind); return; }

   // orizzonti forward (minuti), ordinati crescenti
   int H[3]; int nH=0;
   { int cand[3]={InpH1,InpH2,InpH3};
     for(int q=0;q<3;q++) if(cand[q]>0) H[nH++]=cand[q];
     for(int a=0;a<nH;a++) for(int b=a+1;b<nH;b++) if(H[b]<H[a]){ int tt=H[a]; H[a]=H[b]; H[b]=tt; } }
   int maxH = (nH>0) ? H[nH-1] : 0;
   double up[3], dn[3], ret[3];

   string hP="datetime,line,dir,price,lineVal,d1date,nBelowPrice,rank,spread,spreadVel,cluster,vel,acc,vol";
   for(int q=0;q<nH;q++)
   {
      string hs=IntegerToString(H[q]);
      hP += ",up"+hs+",dn"+hs+",ret"+hs;
   }
   FileWrite(fhP,hP);

   int    prevSide[NLEV];
   for(int k=0;k<NLEV;k++) prevSide[k]=0;
   int    curDay=-1;
   int    pcRows=0;
   long   m1seen=0;
   datetime lastT=0;
   int    p=0;            // puntatore ASCENDENTE su ascT (persistente tra i chunk)

   datetime cur = g_startTime;
   while(cur <= g_endTime)
   {
      datetime chunkEnd = cur + 30*86400;          // finestra di 30 giorni per limitare la memoria
      if(chunkEnd>g_endTime) chunkEnd=g_endTime;
      // carica una CODA extra (maxH minuti) cosi' il forward degli ultimi eventi
      // del chunk ha i dati: gli eventi vengono emessi solo fino a chunkEnd.
      datetime loadEnd = chunkEnd + (datetime)maxH*60 + 60;

      MqlRates r[]; ArraySetAsSeries(r,false);     // false => 0 = piu' vecchio
      int n=-1;
      for(int att=0; att<3; att++){ n=CopyRates(_Symbol,PERIOD_M1,cur,loadEnd,r); if(n>0) break; Sleep(100); }
      Comment(StringFormat("PRICECROSS: %s | eventi=%d | M1 letti=%d",TimeToString(cur,TIME_DATE),pcRows,(int)m1seen));
      if(n>0)
      {
         for(int i=0;i<n;i++)
         {
            datetime tm = r[i].time;
            if(tm>chunkEnd) break;                  // il resto e' solo coda per il look-forward
            if(tm<=lastT) continue;                 // evita la barra di confine duplicata
            lastT=tm;
            m1seen++;
            if((m1seen%100000)==0) Comment(StringFormat("PRICECROSS: %d eventi | M1 letti=%d ...",pcRows,(int)m1seen));

            // mapping M1 -> D1 con puntatore O(1) (niente iBarShift nel loop)
            if(tm<ascT[0]) continue;                // prima dello storico D1
            while(p+1<g_d1Bars && ascT[p+1]<=tm) p++;
            int dd = g_d1Bars-1-p;                  // indice series del giorno corrente
            if(dd<0 || dd>=g_d1Bars) continue;

            double cl = r[i].close;
            if(!IsPriceOk(cl)) continue;

            if(dd!=curDay)
            {
               // nuova D1: ricalibra la baseline sulle linee del giorno (no eventi sul primo M1)
               curDay=dd;
               for(int k=0;k<NLEV;k++){ double L=g_lev[dd][k]; prevSide[k]=IsPriceOk(L)?Sgn(cl,L):0; }
               continue;
            }

            int nBelow=0;
            for(int k=0;k<NLEV;k++){ double L=g_lev[dd][k]; if(IsPriceOk(L)&&cl>L) nBelow++; }

            bool fwdDone=false;                      // escursione forward calcolata 1 volta per barra
            for(int k=0;k<NLEV;k++)
            {
               double L=g_lev[dd][k];
               if(!IsPriceOk(L)) continue;
               int side=Sgn(cl,L);
               if(side!=0 && prevSide[k]!=0 && side!=prevSide[k])
               {
                  if(!fwdDone){ ForwardExc(r,n,i,cl,H,nH,up,dn,ret); fwdDone=true; }
                  string row = TimeToString(tm)
                     +","+gLab[k]
                     +","+IntegerToString(side)
                     +","+DoubleToString(cl,_Digits)
                     +","+DoubleToString(L,_Digits)
                     +","+TimeToString(ascT[p])
                     +","+IntegerToString(nBelow)
                     +","+g_rank[dd]
                     +","+DoubleToString(g_spread[dd],6)
                     +","+DoubleToString(g_spreadVel[dd],6)
                     +","+DoubleToString(g_clu[dd],4)
                     +","+DoubleToString(g_vel[dd],4)
                     +","+DoubleToString(g_acc[dd],4)
                     +","+DoubleToString(g_vol[dd],4);
                  for(int q=0;q<nH;q++)
                     row += ","+DoubleToString(up[q],4)+","+DoubleToString(dn[q],4)+","+DoubleToString(ret[q],4);
                  FileWrite(fhP,row);
                  pcRows++;
               }
               if(side!=0) prevSide[k]=side;
            }
         }
      }
      FileFlush(fhP);                     // salva su disco a ogni chunk (monitorabile + niente perdite)
      if(chunkEnd>=g_endTime) break;
      cur = chunkEnd + 1;
   }
   FileClose(fhP);
   Print(StringFormat(">>> PRICECROSS: %s | %d eventi (M1 letti=%d)",fPC,pcRows,(int)m1seen));

   Comment(StringFormat("EXPORT EVENTS OK: STATE=%d righe | PRICECROSS=%d eventi",stateRows,pcRows));
   IndicatorRelease(g_ind);
}
//+------------------------------------------------------------------+
