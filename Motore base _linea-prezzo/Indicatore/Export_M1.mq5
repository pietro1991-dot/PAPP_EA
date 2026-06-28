//+------------------------------------------------------------------+
//|                                                      Export_M1.mq5 |
//|                                                        PaPP v2     |
//|  Esporta OHLC M1 + SPREAD REALE per barra in CSV, per la pipeline  |
//|  analyze_structural.py (comando 'regime') via m1_to_parquet.py.    |
//|                                                                    |
//|  Colonne: datetime,open,high,low,close,tick_volume,spread_pts      |
//|  datetime = "YYYY.MM.DD HH:MM" (formato atteso dal convertitore).  |
//|  spread_pts = spread in PUNTI alla chiusura della barra (MqlRates).|
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Export OHLC M1 + spread reale per barra -> CSV"
#property script_show_inputs

input string InpSymbol = "";              // vuoto = simbolo del grafico
input string InpStartDate = "2015.01.01"; // inizio (YYYY.MM.DD)
input string InpEndDate   = "2026.06.20"; // fine
input string InpFileName  = "EURUSD_M1.csv";

//+------------------------------------------------------------------+
void OnStart()
  {
   string sym = (InpSymbol=="") ? _Symbol : InpSymbol;
   datetime t0 = StringToTime(InpStartDate);
   datetime t1 = StringToTime(InpEndDate) + 86399;  // fine giornata
   if(t0<=0 || t1<=t0) { Print("ERRORE: date non valide"); return; }

   // assicura che il simbolo sia disponibile e la history M1 sia richiesta
   if(!SymbolSelect(sym,true)) { Print("ERRORE: simbolo ",sym," non disponibile"); return; }
   int dig = (int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
   if(dig<=0) dig = _Digits;

   // tocca la history per innescare il caricamento (M1 puo' essere scaricata on-demand)
   MqlRates probe[];
   CopyRates(sym,PERIOD_M1,t0,t1,probe);
   for(int att=0; att<50 && ArraySize(probe)<=0; att++)
     {
      Sleep(200);
      CopyRates(sym,PERIOD_M1,t0,t1,probe);
     }
   if(ArraySize(probe)<=0)
     {
      Print("ERRORE: nessuna barra M1 nel range. Apri un grafico M1 di ",sym,
            " e scorri indietro per scaricare la history, poi rilancia.");
      return;
     }

   int fh = FileOpen(InpFileName, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
   if(fh==INVALID_HANDLE) { Print("ERRORE file: ",GetLastError()); return; }
   FileWrite(fh,"datetime","open","high","low","close","tick_volume","spread_pts");

   // Esporta a blocchi mensili: evita array M1 giganti su piu' anni.
   long total = 0;
   datetime lastWritten = 0;
   datetime chunkStart = t0;
   const long STEP = 30*86400;   // ~1 mese per blocco

   while(chunkStart <= t1)
     {
      datetime chunkEnd = chunkStart + STEP;
      if(chunkEnd > t1) chunkEnd = t1;

      MqlRates r[];
      int n = CopyRates(sym,PERIOD_M1,chunkStart,chunkEnd,r);
      if(n>0)
        {
         for(int i=0;i<n;i++)
           {
            if(r[i].time <= lastWritten) continue;       // niente duplicati ai bordi
            FileWrite(fh,
               TimeToString(r[i].time, TIME_DATE|TIME_MINUTES),
               DoubleToString(r[i].open, dig),
               DoubleToString(r[i].high, dig),
               DoubleToString(r[i].low,  dig),
               DoubleToString(r[i].close,dig),
               (long)r[i].tick_volume,
               (int)r[i].spread);                        // spread in PUNTI
            lastWritten = r[i].time;
            total++;
           }
         if((total % 50000) < (ulong)n)
            Comment(StringFormat("Export M1 %s: %I64d barre... (%s)",
                    sym, total, TimeToString(lastWritten,TIME_DATE)));
        }
      chunkStart = chunkEnd + 60;   // avanza oltre l'ultimo bar del blocco
     }

   FileClose(fh);
   Comment("");
   Print(StringFormat(">>> EXPORT M1 COMPLETATO: %s | %I64d barre | %s -> %s",
         InpFileName, total, TimeToString(t0), TimeToString(t1)));
   Print("File in: <cartella dati MT5>/MQL5/Files/", InpFileName);
  }
//+------------------------------------------------------------------+
