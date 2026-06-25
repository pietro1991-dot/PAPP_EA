//+------------------------------------------------------------------+
//|                                             EA_IntradayLogger.mq5 |
//|                                            PaPP v2 - INTRADAY      |
//+------------------------------------------------------------------+
//| SISTEMA SEPARATO, NON ANCORATO A D1. EA DI SOLO LOGGING.          |
//|                                                                  |
//| Calcola 4 MA a scala INTRADAY direttamente su M1 (reattive),     |
//| default 15/60/240/480 minuti (15m/1h/4h/8h) + la loro mediana.   |
//| Mira a catturare micro-pattern dove conta la reattivita' delle   |
//| linee al minuto - cosa che il sistema ancorato a D1 non da'.     |
//|                                                                  |
//| Da eseguire nello Strategy Tester su M1 (storico completo) o     |
//| live. NON entra mai a mercato. Output in Common\Files:           |
//|                                                                  |
//|  INTRADAY_<SYM>.csv   1 riga per barra M1 chiusa:               |
//|     OHLC + tick_volume                                            |
//|     Imed + 4 MA intraday                                          |
//|     cluster, vel, acc, vol, spread, spreadVel (su scala M1)       |
//|     dMed..d<p> (distanza % prezzo<->linea), nBelowPrice, rank     |
//|  META_INTRADAY_<SYM>.csv  impronta del dataset                    |
//|                                                                  |
//| Tester consigliato: modello "Solo prezzi di apertura" (rapido    |
//| ed esatto: logghiamo solo barre M1 CHIUSE).                       |
//+------------------------------------------------------------------+
#property copyright "PaPP v2 - INTRADAY"
#property version   "1.00"
#property description "Logger intraday NON ancorato: 4 MA su M1 (15/60/240/480m) + metriche. Non fa trade."

input int  InpP1 = 15;     // MA 1 (minuti)
input int  InpP2 = 60;     // MA 2 (minuti)
input int  InpP3 = 240;    // MA 3 (minuti)
input int  InpP4 = 480;    // MA 4 (minuti)
input bool InpUseCommon = true;   // scrivi in Common\Files

#define NMA   4
#define NLEV  5            // 4 MA + mediana
#define KSLOPE 5
#define NVOL   14
#define NMAX   (NVOL+3)    // storia MA necessaria per vel/acc/vol

int      gPer[NMA];
string   gLab[NLEV];       // etichette: periodi + "M"
int      hMA[NMA] = {INVALID_HANDLE,INVALID_HANDLE,INVALID_HANDLE,INVALID_HANDLE};
int      fhI=INVALID_HANDLE;
datetime g_lastM1=0;
long     m1Rows=0;
datetime g_firstM1log=0, g_lastM1log=0;

//+------------------------------------------------------------------+
bool IsVal(double v){ return (v>0.0 && v<1.0e12); }

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
   gPer[0]=InpP1; gPer[1]=InpP2; gPer[2]=InpP3; gPer[3]=InpP4;
   for(int i=0;i<NMA;i++)
   {
      if(gPer[i]<1){ Print("ERRORE: periodo non valido ",gPer[i]); return INIT_FAILED; }
      hMA[i]=iMA(_Symbol,PERIOD_M1,gPer[i],0,MODE_SMA,PRICE_CLOSE);
      if(hMA[i]==INVALID_HANDLE){ Print("ERRORE iMA period=",gPer[i]); return INIT_FAILED; }
      gLab[i]=IntegerToString(gPer[i]);
   }
   gLab[4]="M";

   int flags = FILE_WRITE|FILE_CSV|FILE_ANSI|(InpUseCommon?FILE_COMMON:0);
   fhI = FileOpen(StringFormat("INTRADAY_%s.csv",_Symbol),flags,",");
   if(fhI==INVALID_HANDLE){ Print("ERRORE apertura INTRADAY: ",GetLastError()); return INIT_FAILED; }

   string h = "datetime,open,high,low,close,tick_volume,Imed";
   for(int i=0;i<NMA;i++) h += ",I"+gLab[i];
   h += ",cluster,vel,acc,vol,spread,spreadVel,dMed";
   for(int i=0;i<NMA;i++) h += ",d"+gLab[i];
   h += ",nBelowPrice,rank,spread_pts";
   FileWrite(fhI,h);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
string RankNow(const double &lev[])
{
   int idx[NLEV]; double val[NLEV]; int c=0;
   for(int k=0;k<NLEV;k++){ if(IsVal(lev[k])){ idx[c]=k; val[c]=lev[k]; c++; } }
   for(int a=0;a<c;a++) for(int b=a+1;b<c;b++) if(val[b]>val[a]){ double tv=val[a]; val[a]=val[b]; val[b]=tv; int ti=idx[a]; idx[a]=idx[b]; idx[b]=ti; }
   string r="";
   for(int a=0;a<c;a++){ r+=gLab[idx[a]]; if(a<c-1) r+=">"; }
   return r;
}

//+------------------------------------------------------------------+
void OnNewM1Bar()
{
   if(BarsCalculated(hMA[NMA-1])<=0) return;

   // storia delle 4 MA allineata alla barra M1 CHIUSA (shift 1 -> ma[*][0])
   double ma[NMA][NMAX];
   for(int i=0;i<NMA;i++)
   {
      double tmp[]; ArraySetAsSeries(tmp,true);
      int got=CopyBuffer(hMA[i],0,1,NMAX,tmp);
      if(got<=0) return;
      for(int s=0;s<NMAX;s++) ma[i][s] = (s<got && IsVal(tmp[s])) ? tmp[s] : 0.0;
   }

   // livelli correnti (barra chiusa): 4 MA + mediana
   double lev[NLEV];
   for(int i=0;i<NMA;i++) lev[i]=ma[i][0];
   double v4[NMA]; int c4=0;
   for(int i=0;i<NMA;i++) if(IsVal(lev[i])) v4[c4++]=lev[i];
   double med = (c4>0)?MedArr(v4,c4):0.0;
   lev[4]=med;

   // barra M1 chiusa
   datetime mt = iTime(_Symbol,PERIOD_M1,1);
   double   mo = iOpen(_Symbol,PERIOD_M1,1);
   double   mh = iHigh(_Symbol,PERIOD_M1,1);
   double   ml = iLow(_Symbol,PERIOD_M1,1);
   double   mc = iClose(_Symbol,PERIOD_M1,1);
   long     mv = iVolume(_Symbol,PERIOD_M1,1);
   if(!IsVal(mc)) return;
   MqlRates rr[]; long msp = 0;
   if(CopyRates(_Symbol,PERIOD_M1,1,1,rr) == 1) msp = rr[0].spread;

   // --- metriche su scala M1 (stesse formule del sistema D1, adattate) ---
   // cluster: dispersione media delle 4 MA attorno alla loro mediana
   double clu=0;
   if(IsVal(med) && c4>=2){ double ds=0; for(int i=0;i<c4;i++) ds+=MathAbs(v4[i]-med)/med*100.0; clu=ds/c4; }

   // vel: |mediana della variazione % su KSLOPE barre|
   double tmpv[NMA]; int tc=0;
   for(int i=0;i<NMA;i++){ double a=ma[i][0],b=ma[i][KSLOPE]; if(IsVal(a)&&IsVal(b)&&b>0) tmpv[tc++]=(a-b)/b*100.0; }
   double vel=(tc>0)?MathAbs(MedArr(tmpv,tc)):0.0;

   // acc: |mediana della differenza seconda su KSLOPE|
   tc=0;
   for(int i=0;i<NMA;i++){ double a=ma[i][0],b=ma[i][KSLOPE],d=ma[i][2*KSLOPE]; if(IsVal(a)&&IsVal(b)&&IsVal(d)&&d>0) tmpv[tc++]=(a-2.0*b+d)/d*100.0; }
   double acc=(tc>0)?MathAbs(MedArr(tmpv,tc)):0.0;

   // vol: mediana della dev.std dei rendimenti su NVOL barre
   tc=0;
   for(int i=0;i<NMA;i++)
   {
      double rr[NVOL]; int rc=0;
      for(int t=0;t<NVOL && t+1<NMAX;t++){ double a=ma[i][t],b=ma[i][t+1]; if(IsVal(a)&&IsVal(b)&&b>0) rr[rc++]=(a-b)/b*100.0; }
      if(rc>=2){ double mn=0; for(int q=0;q<rc;q++) mn+=rr[q]; mn/=rc; double s2=0; for(int q=0;q<rc;q++){ double dd=rr[q]-mn; s2+=dd*dd; } tmpv[tc++]=MathSqrt(s2/(rc-1)); }
   }
   double vol=(tc>0)?MedArr(tmpv,tc):0.0;

   // spread frattale: veloci (P1,P2) - lente (P3,P4)
   double spread=0, spreadVel=0;
   if(IsVal(lev[0])&&IsVal(lev[1])&&IsVal(lev[2])&&IsVal(lev[3]))
   {
      double fast=(lev[0]+lev[1])/2.0, slow=(lev[2]+lev[3])/2.0;
      spread=fast-slow;
      double a0=ma[0][KSLOPE],a1=ma[1][KSLOPE],a2=ma[2][KSLOPE],a3=ma[3][KSLOPE];
      if(IsVal(a0)&&IsVal(a1)&&IsVal(a2)&&IsVal(a3))
      {
         double fK=(a0+a1)/2.0, sK=(a2+a3)/2.0;
         spreadVel=spread-(fK-sK);
      }
   }

   // distanze % prezzo<->linea
   double dMed=(IsVal(med))?(mc-med)/med*100.0:0;
   double dd[NMA];
   for(int i=0;i<NMA;i++) dd[i]=(IsVal(lev[i]))?(mc-lev[i])/lev[i]*100.0:0;

   int nBelow=0;
   for(int k=0;k<NLEV;k++){ if(IsVal(lev[k]) && mc>lev[k]) nBelow++; }

   string row = TimeToString(mt)
      +","+DoubleToString(mo,_Digits)
      +","+DoubleToString(mh,_Digits)
      +","+DoubleToString(ml,_Digits)
      +","+DoubleToString(mc,_Digits)
      +","+IntegerToString(mv)
      +","+DoubleToString(med,_Digits);
   for(int i=0;i<NMA;i++) row += ","+DoubleToString(lev[i],_Digits);
   row += ","+DoubleToString(clu,4)
      +","+DoubleToString(vel,4)
      +","+DoubleToString(acc,4)
      +","+DoubleToString(vol,4)
      +","+DoubleToString(spread,6)
      +","+DoubleToString(spreadVel,6)
      +","+DoubleToString(dMed,4);
   for(int i=0;i<NMA;i++) row += ","+DoubleToString(dd[i],4);
   row += ","+IntegerToString(nBelow)+","+RankNow(lev)+","+IntegerToString((int)msp);

   FileWrite(fhI,row);
   m1Rows++;
   if(g_firstM1log==0) g_firstM1log=mt;
   g_lastM1log=mt;

   if((m1Rows%5000)==0)
   {
      FileFlush(fhI);
      Comment(StringFormat("EA_IntradayLogger: M1=%d | %s",(int)m1Rows,TimeToString(mt,TIME_DATE)));
   }
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime tm0 = iTime(_Symbol,PERIOD_M1,0);
   if(tm0!=g_lastM1)
   {
      if(g_lastM1!=0) OnNewM1Bar();
      g_lastM1 = tm0;
   }
}

//+------------------------------------------------------------------+
void WriteMeta()
{
   int flags = FILE_WRITE|FILE_CSV|FILE_ANSI|(InpUseCommon?FILE_COMMON:0);
   int fh=FileOpen(StringFormat("META_INTRADAY_%s.csv",_Symbol),flags,",");
   if(fh==INVALID_HANDLE) return;
   bool tester=(bool)MQLInfoInteger(MQL_TESTER);
   long off=(long)(TimeCurrent()-TimeGMT())/3600;
   FileWrite(fh,"key","value");
   FileWrite(fh,"system","INTRADAY (non ancorato)");
   FileWrite(fh,"symbol",_Symbol);
   FileWrite(fh,"broker_company",AccountInfoString(ACCOUNT_COMPANY));
   FileWrite(fh,"broker_server",AccountInfoString(ACCOUNT_SERVER));
   FileWrite(fh,"context",tester?"tester":"live");
   FileWrite(fh,"server_gmt_offset_hours",IntegerToString((int)off));
   FileWrite(fh,"ma_periods_min",StringFormat("%d|%d|%d|%d",gPer[0],gPer[1],gPer[2],gPer[3]));
   FileWrite(fh,"ma_type","SMA");
   FileWrite(fh,"timeframe","M1");
   FileWrite(fh,"digits",IntegerToString(_Digits));
   FileWrite(fh,"point",DoubleToString(_Point,_Digits));
   FileWrite(fh,"data_first_m1",g_firstM1log>0?TimeToString(g_firstM1log):"n/a");
   FileWrite(fh,"data_last_m1", g_lastM1log >0?TimeToString(g_lastM1log) :"n/a");
   FileWrite(fh,"m1_rows",IntegerToString((int)m1Rows));
   FileWrite(fh,"export_time_server",TimeToString(TimeCurrent()));
   FileClose(fh);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   WriteMeta();
   if(fhI!=INVALID_HANDLE){ FileClose(fhI); fhI=INVALID_HANDLE; }
   for(int i=0;i<NMA;i++) if(hMA[i]!=INVALID_HANDLE){ IndicatorRelease(hMA[i]); hMA[i]=INVALID_HANDLE; }
   Print(StringFormat(">>> EA_IntradayLogger fine: M1=%d righe",(int)m1Rows));
}
//+------------------------------------------------------------------+
