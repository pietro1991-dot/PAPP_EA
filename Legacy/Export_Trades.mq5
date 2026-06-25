//+------------------------------------------------------------------+
//|                                                 Export_Trades.mq5 |
//|                                                        PaPP v2    |
//+------------------------------------------------------------------+
//| Esporta lo storico dei DEAL del conto in CSV, per correlare i    |
//| trade realmente eseguiti con gli eventi di Export_Events.mq5.    |
//|                                                                  |
//|   -> TRADES_<SIMBOLO>.csv  in MQL5/Files                          |
//|                                                                  |
//| Una riga per deal (IN = apertura, OUT = chiusura). Per ricostru- |
//| ire il singolo trade aggregare per position_id in Python.        |
//|                                                                  |
//| NB: legge lo storico del CONTO corrente (live/demo). I trade del |
//| solo Strategy Tester NON finiscono nello storico conto: per quel |
//| caso fai loggare i trade dall'EA, oppure gira l'EA su un demo.   |
//+------------------------------------------------------------------+
#property copyright "PaPP v2"
#property version   "1.00"
#property description "Esporta lo storico deal del conto -> TRADES_<sym>.csv"
#property script_show_inputs

input string InpStartDate  = "2000.01.01";   // da
input string InpEndDate    = "2100.01.01";   // a (futuro = fino ad ora)
input bool   InpThisSymbol = true;           // true = solo _Symbol, false = tutti i simboli

//+------------------------------------------------------------------+
string DealTypeStr(long t)
{
   switch((ENUM_DEAL_TYPE)t)
   {
      case DEAL_TYPE_BUY:  return "BUY";
      case DEAL_TYPE_SELL: return "SELL";
      default:             return "OTHER";   // balance/credit/commissione ecc.
   }
}
string DealEntryStr(long e)
{
   switch((ENUM_DEAL_ENTRY)e)
   {
      case DEAL_ENTRY_IN:     return "IN";
      case DEAL_ENTRY_OUT:    return "OUT";
      case DEAL_ENTRY_INOUT:  return "INOUT";
      case DEAL_ENTRY_OUT_BY: return "OUT_BY";
      default:                return "?";
   }
}

//+------------------------------------------------------------------+
void OnStart()
{
   datetime t0 = StringToTime(InpStartDate);
   datetime t1 = StringToTime(InpEndDate);
   if(t1<=0 || t1>TimeCurrent()) t1=TimeCurrent();
   if(t0<0) t0=0;

   if(!HistorySelect(t0,t1)){ Print("ERRORE HistorySelect: ",GetLastError()); return; }

   int total = HistoryDealsTotal();
   if(total<=0){ Print("Nessun deal nello storico del conto nel range."); Comment("Nessun deal trovato."); return; }

   string fname = InpThisSymbol ? StringFormat("TRADES_%s.csv",_Symbol) : "TRADES_ALL.csv";
   int fh = FileOpen(fname,FILE_WRITE|FILE_CSV|FILE_ANSI,",");
   if(fh==INVALID_HANDLE){ Print("ERRORE file: ",GetLastError()); return; }

   FileWrite(fh,
      "deal_ticket","position_id","time","symbol","type","entry",
      "volume","price","sl","tp","commission","swap","profit","magic","comment");

   int written=0;
   for(int i=0;i<total;i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk==0) continue;

      string sym = HistoryDealGetString(tk,DEAL_SYMBOL);
      if(InpThisSymbol && sym!=_Symbol) continue;

      long   type  = HistoryDealGetInteger(tk,DEAL_TYPE);
      // salta i movimenti non di trading (balance/credito) quando filtriamo per simbolo o se senza simbolo
      if(type!=DEAL_TYPE_BUY && type!=DEAL_TYPE_SELL) continue;

      long     posId = HistoryDealGetInteger(tk,DEAL_POSITION_ID);
      long     entry = HistoryDealGetInteger(tk,DEAL_ENTRY);
      datetime dt    = (datetime)HistoryDealGetInteger(tk,DEAL_TIME);
      long     magic = HistoryDealGetInteger(tk,DEAL_MAGIC);
      double   vol   = HistoryDealGetDouble(tk,DEAL_VOLUME);
      double   price = HistoryDealGetDouble(tk,DEAL_PRICE);
      double   sl    = HistoryDealGetDouble(tk,DEAL_SL);
      double   tp    = HistoryDealGetDouble(tk,DEAL_TP);
      double   comm  = HistoryDealGetDouble(tk,DEAL_COMMISSION);
      double   swap  = HistoryDealGetDouble(tk,DEAL_SWAP);
      double   prof  = HistoryDealGetDouble(tk,DEAL_PROFIT);
      string   cmt   = HistoryDealGetString(tk,DEAL_COMMENT);

      int dig = (int)SymbolInfoInteger(sym,SYMBOL_DIGITS);
      if(dig<=0) dig=_Digits;

      FileWrite(fh,
         (long)tk, posId, TimeToString(dt),
         sym, DealTypeStr(type), DealEntryStr(entry),
         DoubleToString(vol,2), DoubleToString(price,dig),
         DoubleToString(sl,dig), DoubleToString(tp,dig),
         DoubleToString(comm,2), DoubleToString(swap,2), DoubleToString(prof,2),
         magic, cmt);
      written++;
   }
   FileClose(fh);

   string msg = StringFormat("TRADES export OK: %s | %d deal",fname,written);
   Print(">>> ",msg);
   Comment(msg);
}
//+------------------------------------------------------------------+
