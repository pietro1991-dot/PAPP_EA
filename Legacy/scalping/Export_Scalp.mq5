//+------------------------------------------------------------------+
//|  Export_Scalp.mq5  —  PHAI Scalping (v1.0)                        |
//|                                                                  |
//|  Esporta, PER OGNI BARRA M5, le TUE linee (D1-anchored via        |
//|  PaPP_Median) + le feature d'esecuzione intraday:                 |
//|    - distanza del prezzo M5 da ogni linea (in punti)              |
//|    - cross M5 vs ogni linea (il prezzo M5 attraversa la linea D1)  |
//|    - ADX / +DI / -DI, ATR, ora e sessione                         |
//|                                                                  |
//|  USO: attacca questo SCRIPT a un grafico EURUSD M5.               |
//|  Richiede PaPP_Median.ex5 in MQL5/Indicators.                     |
//+------------------------------------------------------------------+
#property copyright "PHAI"
#property version   "1.00"
#property script_show_inputs
#property description "PHAI Scalp: linee D1 (PaPP_Median) su barre M5 + cross M5, ADX, ATR, sessione."

input string InpIndicatorName = "PaPP_Median.ex5"; // stesso indicatore del Motore Base
input string InpStartDate     = "2018.01.01";      // storia M5 spesso limitata dal broker
input string InpEndDate       = "2026.06.20";
input string InpFileName      = "scalp_EURUSD_M5.csv"; // finisce in MQL5/Files
input int    InpADXperiod     = 14;
input int    InpATRperiod     = 14;

#define BUF_MEDIAN 0
#define BUF_MA365  1
#define BUF_MA182  2
#define BUF_MA121  3
#define BUF_MA30   4
#define BUF_MA14   5
#define BUF_MA7    6
#define BUF_MA3    7

//+------------------------------------------------------------------+
// +1 = il prezzo attraversa la linea verso l'ALTO; -1 verso il BASSO; 0 = niente
int CrossFlag(double prevClose,double prevLine,double curClose,double curLine)
{
   if(prevClose<prevLine && curClose>=curLine) return  1;
   if(prevClose>prevLine && curClose<=curLine) return -1;
   return 0;
}

//+------------------------------------------------------------------+
// Sessione grezza in ORA-SERVER (rivedila in Python in base al TZ del broker).
// 0=Asia, 1=Londra, 2=New York, 3=overlap Londra/NY
int SessionCode(int hh)
{
   if(hh>=13 && hh<16) return 3;
   if(hh>=8  && hh<16) return 1;
   if(hh>=13 && hh<21) return 2;
   return 0;
}

//+------------------------------------------------------------------+
void OnStart()
{
   // le TUE linee: stessi input dell'EA del Motore Base (valori RAW a gradino, no look-ahead)
   int ind = iCustom(_Symbol,_Period,InpIndicatorName, 9, false, true, true, C'20,20,25', true);
   if(ind==INVALID_HANDLE){ Print("ERRORE: iCustom PaPP_Median fallito. Copia PaPP_Median.ex5 in MQL5/Indicators."); return; }
   int hAdx = iADX(_Symbol,_Period,InpADXperiod);
   int hAtr = iATR(_Symbol,_Period,InpATRperiod);
   if(hAdx==INVALID_HANDLE || hAtr==INVALID_HANDLE){ Print("ERRORE: iADX/iATR"); IndicatorRelease(ind); return; }

   // attendi che tutti gli indicatori siano calcolati
   for(int a=0; a<200; a++)
   {
      if(BarsCalculated(ind)>100 && BarsCalculated(hAdx)>100 && BarsCalculated(hAtr)>100) break;
      Sleep(100);
   }

   int total = Bars(_Symbol,_Period);
   if(total<200){ Print("Poche barre M5 (",total,"). Carica piu' storia (scrolla indietro / Max barre = illimitato)."); return; }

   double o[],h[],l[],c[];
   datetime tt[];
   int sp[];
   double bM[],b365[],b182[],b121[],b30[],b14[],b7[],b3[];
   double adxM[],pdi[],mdi[],atrM[];

   ArraySetAsSeries(o,true);   ArraySetAsSeries(h,true);   ArraySetAsSeries(l,true);
   ArraySetAsSeries(c,true);   ArraySetAsSeries(tt,true);  ArraySetAsSeries(sp,true);
   ArraySetAsSeries(bM,true);  ArraySetAsSeries(b365,true);ArraySetAsSeries(b182,true);
   ArraySetAsSeries(b121,true);ArraySetAsSeries(b30,true); ArraySetAsSeries(b14,true);
   ArraySetAsSeries(b7,true);  ArraySetAsSeries(b3,true);
   ArraySetAsSeries(adxM,true);ArraySetAsSeries(pdi,true); ArraySetAsSeries(mdi,true); ArraySetAsSeries(atrM,true);

   int n = total;
   n = MathMin(n, CopyOpen (_Symbol,_Period,0,total,o));
   n = MathMin(n, CopyHigh (_Symbol,_Period,0,total,h));
   n = MathMin(n, CopyLow  (_Symbol,_Period,0,total,l));
   n = MathMin(n, CopyClose(_Symbol,_Period,0,total,c));
   n = MathMin(n, CopyTime (_Symbol,_Period,0,total,tt));
   CopySpread(_Symbol,_Period,0,total,sp);   // puo' essere piu' corto: guardia sotto
   n = MathMin(n, CopyBuffer(ind,BUF_MEDIAN,0,total,bM));
   n = MathMin(n, CopyBuffer(ind,BUF_MA365, 0,total,b365));
   n = MathMin(n, CopyBuffer(ind,BUF_MA182, 0,total,b182));
   n = MathMin(n, CopyBuffer(ind,BUF_MA121, 0,total,b121));
   n = MathMin(n, CopyBuffer(ind,BUF_MA30,  0,total,b30));
   n = MathMin(n, CopyBuffer(ind,BUF_MA14,  0,total,b14));
   n = MathMin(n, CopyBuffer(ind,BUF_MA7,   0,total,b7));
   n = MathMin(n, CopyBuffer(ind,BUF_MA3,   0,total,b3));
   n = MathMin(n, CopyBuffer(hAdx,0,0,total,adxM));
   n = MathMin(n, CopyBuffer(hAdx,1,0,total,pdi));
   n = MathMin(n, CopyBuffer(hAdx,2,0,total,mdi));
   n = MathMin(n, CopyBuffer(hAtr,0,0,total,atrM));
   if(n<200){ Print("ERRORE: pochi dati allineati (",n,")"); IndicatorRelease(ind);IndicatorRelease(hAdx);IndicatorRelease(hAtr); return; }

   datetime startT = StringToTime(InpStartDate);
   datetime endT   = StringToTime(InpEndDate)+86399;

   int fh = FileOpen(InpFileName,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fh==INVALID_HANDLE){ Print("ERRORE file: ",GetLastError()); IndicatorRelease(ind);IndicatorRelease(hAdx);IndicatorRelease(hAtr); return; }

   FileWrite(fh,"datetime","open","high","low","close","spread",
      "median","MA365","MA182","MA121","MA30","MA14","MA7","MA3",
      "dMed","d365","d182","d121","d30","d14","d7","d3",
      "xMed","x365","x182","x121","x30","x14","x7","x3",
      "adx","plusDI","minusDI","atr","hour","session");

   double pt = _Point; if(pt<=0.0) pt=0.00001;
   int spN = ArraySize(sp);
   int written = 0;

   // dalla piu' vecchia (n-1) alla piu' recente (1). La barra 0 (in formazione) e' esclusa.
   for(int i=n-2; i>=1; i--)
   {
      if(tt[i]<startT || tt[i]>endT) continue;
      if(!(bM[i]>0.0 && b365[i]>0.0)) continue;   // linee non ancora valide su questa barra
      int p = i+1;

      MqlDateTime mdt; TimeToStruct(tt[i],mdt);

      double dMed=(c[i]-bM[i])/pt,  d365=(c[i]-b365[i])/pt, d182=(c[i]-b182[i])/pt,
             d121=(c[i]-b121[i])/pt,d30=(c[i]-b30[i])/pt,   d14=(c[i]-b14[i])/pt,
             d7=(c[i]-b7[i])/pt,    d3=(c[i]-b3[i])/pt;

      int xMed=CrossFlag(c[p],bM[p],  c[i],bM[i]);
      int x365=CrossFlag(c[p],b365[p],c[i],b365[i]);
      int x182=CrossFlag(c[p],b182[p],c[i],b182[i]);
      int x121=CrossFlag(c[p],b121[p],c[i],b121[i]);
      int x30 =CrossFlag(c[p],b30[p], c[i],b30[i]);
      int x14 =CrossFlag(c[p],b14[p], c[i],b14[i]);
      int x7  =CrossFlag(c[p],b7[p],  c[i],b7[i]);
      int x3  =CrossFlag(c[p],b3[p],  c[i],b3[i]);

      int spread = (i<spN) ? sp[i] : 0;

      FileWrite(fh, TimeToString(tt[i]),
         DoubleToString(o[i],_Digits),DoubleToString(h[i],_Digits),DoubleToString(l[i],_Digits),DoubleToString(c[i],_Digits),
         spread,
         DoubleToString(bM[i],_Digits),DoubleToString(b365[i],_Digits),DoubleToString(b182[i],_Digits),DoubleToString(b121[i],_Digits),
         DoubleToString(b30[i],_Digits),DoubleToString(b14[i],_Digits),DoubleToString(b7[i],_Digits),DoubleToString(b3[i],_Digits),
         DoubleToString(dMed,1),DoubleToString(d365,1),DoubleToString(d182,1),DoubleToString(d121,1),
         DoubleToString(d30,1),DoubleToString(d14,1),DoubleToString(d7,1),DoubleToString(d3,1),
         xMed,x365,x182,x121,x30,x14,x7,x3,
         DoubleToString(adxM[i],2),DoubleToString(pdi[i],2),DoubleToString(mdi[i],2),DoubleToString(atrM[i]/pt,1),
         mdt.hour, SessionCode(mdt.hour));
      written++;
   }

   FileClose(fh);
   Comment(StringFormat("EXPORT SCALP OK: %s | %d righe M5",InpFileName,written));
   Print(StringFormat(">>> EXPORT SCALP OK: %s | %d righe M5 (%s)",InpFileName,written,_Symbol));
   IndicatorRelease(ind); IndicatorRelease(hAdx); IndicatorRelease(hAtr);
}
