//+------------------------------------------------------------------+
//|                                                     EA_Logger.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
//| EA DI SOLO LOGGING — NON ENTRA MAI A MERCATO.                     |
//|                                                                  |
//| Da eseguire nello Strategy Tester su timeframe M1: il tester     |
//| fornisce TUTTO lo storico M1 del periodo (uno script vede solo   |
//| la cache del terminale, l'EA-in-tester no).                       |
//|                                                                  |
//| Registra in modo COMPLETO e LOSSLESS, in Common\Files:           |
//|                                                                  |
//|  M1LOG_<SYM>.csv   1 riga PER OGNI barra M1 chiusa:              |
//|     OHLC + tick_volume                                            |
//|     8 livelli (median + 7 MA), come EVOLVONO intraday             |
//|     cluster, vel(velocita'), acc(accelerazione), vol(volatilita') |
//|        lette DIRETTAMENTE dai buffer dell'indicatore              |
//|     spread, spreadVel (frattale)                                  |
//|     dMed..d3 (distanza % prezzo<->ogni linea), nBelowPrice, rank  |
//|                                                                  |
//|  STATE_D1_<SYM>.csv  1 riga per barra D1 (riepilogo geometrico    |
//|     sui valori D1 CHIUSI: 28 posizioni + 28 incroci linea-linea   |
//|     + metriche). Opzionale (InpWriteState).                       |
//|                                                                  |
//| FILOSOFIA: l'EA cattura gli ATOMI grezzi esatti. Escursione       |
//| forward (MAE/MFE), incroci prezzo-linea, ranking storico, ecc.    |
//| sono funzioni deterministiche di questi dati -> si calcolano in   |
//| Python, con piena liberta' e senza ri-girare MT5.                 |
//|                                                                  |
//| Tester consigliato: modello "Solo prezzi di apertura" -> rapido   |
//| ed ESATTO: logghiamo solo barre M1 gia' CHIUSE (OHLC definitivo). |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "2.01"
#property description "Logger PaPP completo: M1LOG (tutto per ogni M1) + STATE_D1. Non fa trade. Tester su M1."

input string InpIndicatorName = "PaPP_Median.ex5";
input bool   InpWriteState    = true;   // scrivi anche STATE_D1 (riepilogo giornaliero)
input bool   InpUseCommon     = true;   // scrivi in Common\Files (consigliato nel tester)

#define ANCHOR_TF PERIOD_D1
#define KSLOPE 5
#define NVOL   14
#define CLWIN  252
#define NLEV   8
#define HBUF   (CLWIN+2*KSLOPE+NVOL+5)

// buffer iCustom: 0=median,1=MA365,2=MA182,3=MA121,4=MA30,5=MA14,6=MA7,7=MA3
//                 8=cluster,9=vel,10=acc,11=vol
// lev[0..7] = MA365,MA182,MA121,MA30,MA14,MA7,MA3,MED
int    gBuf[NLEV]   = {1,2,3,4,5,6,7,0};
string gLab[NLEV]   = {"365","182","121","30","14","7","3","M"};
#define BUF_CLU 8
#define BUF_VEL 9
#define BUF_ACC 10
#define BUF_VOL 11

int      hInd = INVALID_HANDLE;
int      fhM  = INVALID_HANDLE;   // M1LOG
int      fhS  = INVALID_HANDLE;   // STATE_D1
datetime g_lastM1 = 0;
datetime g_curDay = 0;
int      stateRows=0;
long     m1Rows=0;
datetime g_firstM1log=0, g_lastM1log=0;   // impronta del range effettivamente loggato

// cache metriche del giorno (costanti entro la D1)
double   gClu=0,gVel=0,gAcc=0,gVol=0,gSpread=0,gSpreadVel=0;

//+------------------------------------------------------------------+
bool IsPriceOk(double v){ return (v>0.0 && v<1.0e12); }
int  Sgn(double a,double b){ return (a>b)?1:((a<b)?-1:0); }

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
double Buf1(int buf,int shift)
{
   double tmp[]; ArraySetAsSeries(tmp,true);
   int got=CopyBuffer(hInd,buf,shift,1,tmp);
   return (got>0 && IsPriceOk(tmp[0])) ? tmp[0] : 0.0;
}

//+------------------------------------------------------------------+
// Metriche giornaliere su array D1 locale L[bars][NLEV] (series, 0=recente).
void DailyMetrics(const double &L[][NLEV],int bars,int db,
                  double &spread,double &spreadVel,double &clu,double &vel,double &acc,double &vol)
{
   spread=0; spreadVel=0; clu=0; vel=0; acc=0; vol=0;
   double f=(L[db][6]+L[db][5]+L[db][4])/3.0;
   double s=(L[db][0]+L[db][1]+L[db][2])/3.0;
   spread=f-s;
   if(db+1<bars)
   {
      double fy=(L[db+1][6]+L[db+1][5]+L[db+1][4])/3.0;
      double sy=(L[db+1][0]+L[db+1][1]+L[db+1][2])/3.0;
      spreadVel=spread-(fy-sy);
   }
   if(db+CLWIN+2*KSLOPE+NVOL>=bars) return;

   double sm=0; int cc=0;
   for(int j=db;j<db+CLWIN;j++)
   {
      double vv[7]; int cv=0;
      for(int m=0;m<7;m++){ double x=L[j][m]; if(IsPriceOk(x)) vv[cv++]=x; }
      if(cv>=2){ double md=MedArr(vv,cv); if(md>0){ double ds=0; for(int n=0;n<cv;n++) ds+=MathAbs(vv[n]-md)/md*100.0; sm+=ds/cv; cc++; } }
   }
   if(cc>0) clu=sm/cc;

   double v7[7]; int vc=0;
   for(int m=0;m<7;m++){ double a=L[db][m],b=L[db+KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&b>0) v7[vc++]=(a-b)/b*100.0; }
   if(vc>0) vel=MathAbs(MedArr(v7,vc));
   vc=0;
   for(int m=0;m<7;m++){ double a=L[db][m],b=L[db+KSLOPE][m],d=L[db+2*KSLOPE][m]; if(IsPriceOk(a)&&IsPriceOk(b)&&IsPriceOk(d)&&d>0) v7[vc++]=(a-2.0*b+d)/d*100.0; }
   if(vc>0) acc=MathAbs(MedArr(v7,vc));
   vc=0;
   for(int m=0;m<7;m++)
   {
      double rr[NVOL]; int rc=0;
      for(int t2=db;t2<db+NVOL && t2+1<bars;t2++){ double a=L[t2][m],b2=L[t2+1][m]; if(IsPriceOk(a)&&IsPriceOk(b2)&&b2>0) rr[rc++]=(a-b2)/b2*100.0; }
      if(rc>=2){ double mn=0; for(int q=0;q<rc;q++) mn+=rr[q]; mn/=rc; double s2=0; for(int q=0;q<rc;q++){ double dd=rr[q]-mn; s2+=dd*dd; } v7[vc++]=MathSqrt(s2/(rc-1)); }
   }
   if(vc>0) vol=MedArr(v7,vc);
}

//+------------------------------------------------------------------+
string RankStr2(const double &L[][NLEV],int db)
{
   int idx[NLEV]; double val[NLEV]; int c=0;
   for(int k=0;k<NLEV;k++){ if(IsPriceOk(L[db][k])){ idx[c]=k; val[c]=L[db][k]; c++; } }
   for(int a=0;a<c;a++) for(int b=a+1;b<c;b++) if(val[b]>val[a]){ double tv=val[a]; val[a]=val[b]; val[b]=tv; int ti=idx[a]; idx[a]=idx[b]; idx[b]=ti; }
   string r="";
   for(int a=0;a<c;a++){ r+=gLab[idx[a]]; if(a<c-1) r+=">"; }
   return r;
}
//+------------------------------------------------------------------+
string RankNow(const double &lev[])
{
   int idx[NLEV]; double val[NLEV]; int c=0;
   for(int k=0;k<NLEV;k++){ if(IsPriceOk(lev[k])){ idx[c]=k; val[c]=lev[k]; c++; } }
   for(int a=0;a<c;a++) for(int b=a+1;b<c;b++) if(val[b]>val[a]){ double tv=val[a]; val[a]=val[b]; val[b]=tv; int ti=idx[a]; idx[a]=idx[b]; idx[b]=ti; }
   string r="";
   for(int a=0;a<c;a++){ r+=gLab[idx[a]]; if(a<c-1) r+=">"; }
   return r;
}

//+------------------------------------------------------------------+
int OnInit()
{
   hInd = iCustom(_Symbol,ANCHOR_TF,InpIndicatorName,
      9, false, true, true, C'20,20,25', true);
   if(hInd==INVALID_HANDLE){ Print("ERRORE: iCustom fallito"); return INIT_FAILED; }

   int flags = FILE_WRITE|FILE_CSV|FILE_ANSI|(InpUseCommon?FILE_COMMON:0);

   fhM = FileOpen(StringFormat("M1LOG_%s.csv",_Symbol),flags,",");
   if(fhM==INVALID_HANDLE){ Print("ERRORE apertura M1LOG: ",GetLastError()); return INIT_FAILED; }

   // header M1LOG
   string hM = "datetime,d1open,open,high,low,close,tick_volume,"
               "median,MA365,MA182,MA121,MA30,MA14,MA7,MA3,"
               "cluster,vel,acc,vol,spread,spreadVel,"
               "dMed,d365,d182,d121,d30,d14,d7,d3,nBelowPrice,rank,spread_pts";
   FileWrite(fhM,hM);

   if(InpWriteState)
   {
      fhS = FileOpen(StringFormat("STATE_D1_%s.csv",_Symbol),flags,",");
      if(fhS==INVALID_HANDLE){ Print("ERRORE apertura STATE_D1: ",GetLastError()); return INIT_FAILED; }
      string hS = "datetime";
      for(int k=0;k<NLEV;k++) hS += ",L"+gLab[k];
      hS += ",rank,spread,spreadVel,cluster,vel,acc,vol";
      for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++) hS += ",p"+gLab[i]+"_"+gLab[j];
      for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++) hS += ",x"+gLab[i]+"_"+gLab[j];
      FileWrite(fhS,hS);
   }
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
// Aggiorna la cache delle metriche del giorno (costanti entro la D1):
// cluster/vel/acc/vol LETTE dai buffer dell'indicatore (valore del giorno
// appena chiuso, come calcola l'indicatore); spread/spreadVel ricalcolati
// con la stessa formula dai valori D1 chiusi (shift 1 e 2).
void RefreshDailyCache()
{
   gClu=Buf1(BUF_CLU,0);
   gVel=Buf1(BUF_VEL,0);
   gAcc=Buf1(BUF_ACC,0);
   gVol=Buf1(BUF_VOL,0);

   double m1[7], m2[7];
   for(int k=0;k<7;k++){ m1[k]=Buf1(gBuf[k],1); m2[k]=Buf1(gBuf[k],2); }
   // veloci = MA3,MA7,MA14 (k=6,5,4) ; lenti = MA365,182,121 (k=0,1,2)
   double f1=(m1[6]+m1[5]+m1[4])/3.0, s1=(m1[0]+m1[1]+m1[2])/3.0;
   double f2=(m2[6]+m2[5]+m2[4])/3.0, s2=(m2[0]+m2[1]+m2[2])/3.0;
   gSpread    = f1-s1;
   gSpreadVel = (f1-s1)-(f2-s2);
}

//+------------------------------------------------------------------+
void EmitState()
{
   if(fhS==INVALID_HANDLE) return;
   double L[][NLEV]; ArrayResize(L,HBUF);
   for(int k=0;k<NLEV;k++)
   {
      double tmp[]; ArraySetAsSeries(tmp,true);
      int got=CopyBuffer(hInd,gBuf[k],0,HBUF,tmp);
      if(got<=0) return;
      for(int s=0;s<HBUF;s++) L[s][k] = (s<got && IsPriceOk(tmp[s])) ? tmp[s] : 0.0;
   }
   int db=1;
   if(!IsPriceOk(L[db][7])) return;

   datetime dt = iTime(_Symbol,ANCHOR_TF,db);
   double spread,spreadVel,clu,vel,acc,vol;
   DailyMetrics(L,HBUF,db,spread,spreadVel,clu,vel,acc,vol);

   string row = TimeToString(dt);
   for(int k=0;k<NLEV;k++) row += ","+DoubleToString(L[db][k],_Digits);
   row += ","+RankStr2(L,db);
   row += ","+DoubleToString(spread,6)+","+DoubleToString(spreadVel,6);
   row += ","+DoubleToString(clu,4)+","+DoubleToString(vel,4)+","+DoubleToString(acc,4)+","+DoubleToString(vol,4);
   for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++)
   {
      int pv = (IsPriceOk(L[db][i])&&IsPriceOk(L[db][j])) ? (L[db][i]>L[db][j]?1:0) : 0;
      row += ","+IntegerToString(pv);
   }
   for(int i=0;i<NLEV;i++) for(int j=i+1;j<NLEV;j++)
   {
      int cross=0;
      if(IsPriceOk(L[db][i])&&IsPriceOk(L[db][j])&&IsPriceOk(L[db+1][i])&&IsPriceOk(L[db+1][j]))
      {
         int sc=Sgn(L[db][i],L[db][j]), sp=Sgn(L[db+1][i],L[db+1][j]);
         if(sc>0 && sp<=0) cross=1; else if(sc<0 && sp>=0) cross=-1;
      }
      row += ","+IntegerToString(cross);
   }
   FileWrite(fhS,row); FileFlush(fhS);
   stateRows++;
}

//+------------------------------------------------------------------+
void OnNewM1Bar()
{
   if(BarsCalculated(hInd)<=0) return;

   // linee correnti (evolvono intraday) dal valore D1 raw shift 0
   double lev[NLEV];
   for(int k=0;k<NLEV;k++) lev[k]=Buf1(gBuf[k],0);
   double median=lev[7];

   // cambio giorno: emetti STATE del giorno chiuso e aggiorna la cache metriche
   datetime d0 = iTime(_Symbol,ANCHOR_TF,0);
   if(d0!=g_curDay)
   {
      if(g_curDay!=0) EmitState();
      RefreshDailyCache();
      g_curDay=d0;
   }

   // barra M1 appena chiusa
   datetime mt = iTime(_Symbol,PERIOD_M1,1);
   double   mo = iOpen(_Symbol,PERIOD_M1,1);
   double   mh = iHigh(_Symbol,PERIOD_M1,1);
   double   ml = iLow(_Symbol,PERIOD_M1,1);
   double   mc = iClose(_Symbol,PERIOD_M1,1);
   long     mv = iVolume(_Symbol,PERIOD_M1,1);
   if(!IsPriceOk(mc)) return;
   // spread REALE della barra chiusa (in points) — il costo vero di quell'ora
   MqlRates rr[]; long msp = 0;
   if(CopyRates(_Symbol,PERIOD_M1,1,1,rr) == 1) msp = rr[0].spread;

   // distanze % prezzo<->linea (mediana + 7 MA, ordine: Med,365,182,121,30,14,7,3)
   double dMed=(IsPriceOk(median))?(mc-median)/median*100.0:0;
   double dd[7];
   for(int k=0;k<7;k++) dd[k]=(IsPriceOk(lev[k]))?(mc-lev[k])/lev[k]*100.0:0;

   int nBelow=0;
   for(int k=0;k<NLEV;k++){ if(IsPriceOk(lev[k]) && mc>lev[k]) nBelow++; }

   string row = TimeToString(mt)
      +","+TimeToString(g_curDay)
      +","+DoubleToString(mo,_Digits)
      +","+DoubleToString(mh,_Digits)
      +","+DoubleToString(ml,_Digits)
      +","+DoubleToString(mc,_Digits)
      +","+IntegerToString(mv)
      +","+DoubleToString(median,_Digits)
      +","+DoubleToString(lev[0],_Digits)   // MA365
      +","+DoubleToString(lev[1],_Digits)   // MA182
      +","+DoubleToString(lev[2],_Digits)   // MA121
      +","+DoubleToString(lev[3],_Digits)   // MA30
      +","+DoubleToString(lev[4],_Digits)   // MA14
      +","+DoubleToString(lev[5],_Digits)   // MA7
      +","+DoubleToString(lev[6],_Digits)   // MA3
      +","+DoubleToString(gClu,4)
      +","+DoubleToString(gVel,4)
      +","+DoubleToString(gAcc,4)
      +","+DoubleToString(gVol,4)
      +","+DoubleToString(gSpread,6)
      +","+DoubleToString(gSpreadVel,6)
      +","+DoubleToString(dMed,4)
      +","+DoubleToString(dd[0],4)+","+DoubleToString(dd[1],4)+","+DoubleToString(dd[2],4)
      +","+DoubleToString(dd[3],4)+","+DoubleToString(dd[4],4)+","+DoubleToString(dd[5],4)
      +","+DoubleToString(dd[6],4)
      +","+IntegerToString(nBelow)
      +","+RankNow(lev)
      +","+IntegerToString((int)msp);
   FileWrite(fhM,row);
   m1Rows++;
   if(g_firstM1log==0) g_firstM1log=mt;
   g_lastM1log=mt;

   if((m1Rows%5000)==0)
   {
      FileFlush(fhM);
      Comment(StringFormat("EA_Logger: M1=%d | STATE=%d | %s",(int)m1Rows,stateRows,TimeToString(mt,TIME_DATE)));
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime tm0 = iTime(_Symbol,PERIOD_M1,0);
   if(tm0!=g_lastM1)
   {
      if(g_lastM1!=0) OnNewM1Bar();   // una barra M1 si e' appena chiusa
      g_lastM1 = tm0;
   }
}

//+------------------------------------------------------------------+
// Sidecar con l'IMPRONTA del dataset: identita' broker + chiusura D1.
// Cosi' il dataset porta con se' "da dove viene" (fondamentale perche'
// i pattern dipendono dall'orario di chiusura D1 del broker).
void WriteMeta()
{
   int flags = FILE_WRITE|FILE_CSV|FILE_ANSI|(InpUseCommon?FILE_COMMON:0);
   int fh=FileOpen(StringFormat("META_%s.csv",_Symbol),flags,",");
   if(fh==INVALID_HANDLE){ Print("META: FileOpen err ",GetLastError()); return; }
   bool tester = (bool)MQLInfoInteger(MQL_TESTER);
   long off = (long)(TimeCurrent()-TimeGMT())/3600;

   FileWrite(fh,"key","value");
   FileWrite(fh,"symbol",_Symbol);
   FileWrite(fh,"broker_company",AccountInfoString(ACCOUNT_COMPANY));
   FileWrite(fh,"broker_server",AccountInfoString(ACCOUNT_SERVER));
   FileWrite(fh,"context",tester?"tester":"live");
   FileWrite(fh,"server_gmt_offset_hours",IntegerToString((int)off));
   FileWrite(fh,"server_gmt_offset_note",
             tester?"in tester TimeGMT=server: offset puo' essere 0 - usa broker_server per l'identita'"
                   :"offset reale server-GMT");
   FileWrite(fh,"anchor_tf","D1");
   FileWrite(fh,"digits",IntegerToString(_Digits));
   FileWrite(fh,"point",DoubleToString(_Point,_Digits));
   FileWrite(fh,"indicator",InpIndicatorName);
   FileWrite(fh,"ind_params","Smooth=false;InpSignals=true;MA=365|182|121|30|14|7|3");
   FileWrite(fh,"data_first_m1", g_firstM1log>0?TimeToString(g_firstM1log):"n/a");
   FileWrite(fh,"data_last_m1",  g_lastM1log >0?TimeToString(g_lastM1log) :"n/a");
   FileWrite(fh,"m1_rows",IntegerToString((int)m1Rows));
   FileWrite(fh,"state_rows",IntegerToString(stateRows));
   FileWrite(fh,"export_time_server",TimeToString(TimeCurrent()));
   FileClose(fh);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   WriteMeta();
   if(fhM!=INVALID_HANDLE){ FileClose(fhM); fhM=INVALID_HANDLE; }
   if(fhS!=INVALID_HANDLE){ FileClose(fhS); fhS=INVALID_HANDLE; }
   if(hInd!=INVALID_HANDLE){ IndicatorRelease(hInd); hInd=INVALID_HANDLE; }
   Print(StringFormat(">>> EA_Logger fine: M1=%d righe | STATE=%d righe",(int)m1Rows,stateRows));
}
//+------------------------------------------------------------------+
