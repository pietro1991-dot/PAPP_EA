//+------------------------------------------------------------------+
//|                                                    Export_OHLC.mq5 |
//|                                                        PaPP v2     |
//+------------------------------------------------------------------+
//| Esporta SOLO OHLC puliti (datetime,open,high,low,close,volume)    |
//| del simbolo e timeframe del grafico su cui viene eseguito.        |
//| Serve per i test price-action (breakout / fade / orizzonte).      |
//|                                                                   |
//| USO:                                                              |
//|   1. Apri il grafico del simbolo voluto (es. EURUSD)              |
//|   2. Imposta il timeframe voluto (es. H1)                         |
//|   3. SCORRI INDIETRO il grafico per caricare lo storico completo  |
//|   4. Trascina questo script sul grafico                           |
//|   -> salva in  MQL5/Files/OHLC_<SIMBOLO>_<TF>.csv                 |
//|      (il nome contiene simbolo e timeframe: nessuna ambiguita')   |
//|                                                                   |
//| Ordine righe: SEMPRE dal piu' VECCHIO al piu' RECENTE (cronologico)|
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Esporta OHLC puliti del grafico corrente. Nome file = OHLC_<sym>_<tf>.csv"
#property script_show_inputs

input ENUM_TIMEFRAMES InpTimeframe = PERIOD_CURRENT;   // Timeframe (default = quello del grafico)
input string          InpStartDate = "2000.01.01";    // Data inizio
input string          InpEndDate   = "2100.01.01";    // Data fine (futuro = fino a oggi)

//+------------------------------------------------------------------+
void OnStart()
{
   ENUM_TIMEFRAMES tf = (InpTimeframe == PERIOD_CURRENT) ? (ENUM_TIMEFRAMES)_Period : InpTimeframe;

   datetime t0 = StringToTime(InpStartDate);
   datetime t1 = StringToTime(InpEndDate);
   if(t1 <= 0 || t1 > TimeCurrent()) t1 = TimeCurrent();
   if(t0 <= 0) t0 = 0;

   // --- Copia le barre nel range (con retry: forza il caricamento dello storico) ---
   MqlRates rates[];
   ArraySetAsSeries(rates, false);          // false => indice 0 = piu' vecchio
   int n = -1;
   for(int att = 0; att < 100; att++)
   {
      n = CopyRates(_Symbol, tf, t0, t1, rates);
      if(n > 0) break;
      Sleep(200);                            // attende il download dello storico
   }
   if(n <= 0)
   {
      Print("ERRORE CopyRates: ", GetLastError(),
            " — scorri il grafico indietro per caricare lo storico, poi riprova.");
      Comment("Export OHLC FALLITO: storico non disponibile. Scorri il grafico indietro.");
      return;
   }

   // --- Garantisce ordine cronologico (vecchio -> recente) ---
   bool oldestFirst = (n < 2 || rates[0].time <= rates[n-1].time);

   // --- Nome file auto: OHLC_<simbolo>_<tf>.csv ---
   string tfname = StringSubstr(EnumToString(tf), 7);   // "PERIOD_H1" -> "H1"
   string fname  = StringFormat("OHLC_%s_%s.csv", _Symbol, tfname);

   int fh = FileOpen(fname, FILE_WRITE|FILE_CSV|FILE_ANSI, ",");
   if(fh == INVALID_HANDLE)
   {
      Print("ERRORE apertura file: ", GetLastError());
      return;
   }

   FileWrite(fh, "datetime", "open", "high", "low", "close", "tick_volume");

   int dig = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   for(int k = 0; k < n; k++)
   {
      int i = oldestFirst ? k : (n - 1 - k);
      FileWrite(fh,
         TimeToString(rates[i].time, TIME_DATE|TIME_MINUTES),
         DoubleToString(rates[i].open,  dig),
         DoubleToString(rates[i].high,  dig),
         DoubleToString(rates[i].low,   dig),
         DoubleToString(rates[i].close, dig),
         (long)rates[i].tick_volume);
   }
   FileClose(fh);

   datetime tFirst = oldestFirst ? rates[0].time   : rates[n-1].time;
   datetime tLast  = oldestFirst ? rates[n-1].time : rates[0].time;
   string msg = StringFormat("OHLC export OK: %s | %d barre | %s -> %s",
                             fname, n, TimeToString(tFirst), TimeToString(tLast));
   Print(">>> ", msg);
   Comment(msg);
}
//+------------------------------------------------------------------+
