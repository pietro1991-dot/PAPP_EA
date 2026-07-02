//+------------------------------------------------------------------+
//|                                                    papp_push.mqh  |
//|  Telemetria PHAI condivisa: ogni EA include questo file e manda   |
//|  i PROPRI eventi (segnali open/close, stato, feature) al server   |
//|  chatbot via WebRequest. Multi-tenant: la license key identifica  |
//|  il cliente. Niente WebRequest nel tester.                        |
//|                                                                    |
//|  Uso:                                                              |
//|    #include "papp_push.mqh"                                        |
//|    OnInit():  PappInit(InpUseServer, InpServerUrl, InpLicenseKey); |
//|    apertura:  PappSignal("open", _Symbol, dir, entry,sl,tp,lot,0,0,reason);|
//|    chiusura:  PappSignal("close",_Symbol, dir, 0,0,0,0, exitPx,pnl, reason);|
//|    feature:   PappFeatures(_Symbol, close, d_med,d_ma30,d_ma365,   |
//|                            clu,vel,acc,vol,orderScore,spread);     |
//|  Ricorda: autorizza l'URL in Strumenti>Opzioni>EA>WebRequest.     |
//+------------------------------------------------------------------+
#ifndef __PAPP_PUSH_MQH__
#define __PAPP_PUSH_MQH__

bool   _pp_use = false;
string _pp_url = "";
string _pp_key = "";

void PappInit(bool useServer, string url, string key)
{
   _pp_use = useServer;
   _pp_url = url;
   _pp_key = key;
}

string PappEsc(string s){ StringReplace(s,"\\","\\\\"); StringReplace(s,"\"","\\\""); return s; }

string PappPost(string path, string body)
{
   if(!_pp_use || MQLInfoInteger(MQL_TESTER)) return "";          // niente WebRequest nel tester
   char post[]; StringToCharArray(body, post, 0, WHOLE_ARRAY, CP_UTF8);
   int sz = ArraySize(post); if(sz > 0 && post[sz-1] == 0) ArrayResize(post, sz-1);
   char result[]; string rh; ResetLastError();
   int code = WebRequest("POST", _pp_url + path, "Content-Type: application/json\r\n",
                         3000, post, result, rh);
   if(code == -1)
   {
      Print("PHAI: WebRequest fallita (err ", GetLastError(), "). Autorizza ", _pp_url,
            " in Strumenti > Opzioni > Expert Advisors > WebRequest.");
      return "";
   }
   return CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
}

// invia un evento JSON (gia' senza le graffe esterne) iniettando la license key
void PappEvent(string jsonFields)
{
   if(!_pp_use || StringLen(_pp_key) == 0 || StringLen(jsonFields) < 2) return;
   string body = "{\"key\":\"" + PappEsc(_pp_key) + "\"," + jsonFields + "}";
   PappPost("/api/ea/ingest", body);
}

// invia una LINEA json gia' completa (che inizia con '{'): inietta la key e posta.
// Usato dagli EA che costruiscono il json una volta (lo scrivono anche nel log locale).
void PappSendLine(string jsonline)
{
   if(!_pp_use || StringLen(_pp_key) == 0 || StringLen(jsonline) < 2) return;
   string body = "{\"key\":\"" + PappEsc(_pp_key) + "\"," + StringSubstr(jsonline, 1);
   PappPost("/api/ea/ingest", body);
}

// parsa una risposta key=value (una per riga) e ritorna il valore della chiave.
string PappKv(string resp, string key)
{
   string lines[]; int n = StringSplit(resp, '\n', lines);
   for(int i = 0; i < n; i++)
   {
      string ln = lines[i]; StringReplace(ln, "\r", "");
      int p = StringFind(ln, "=");
      if(p > 0 && StringSubstr(ln, 0, p) == key) return StringSubstr(ln, p+1);
   }
   return "";
}

// === LOG LOCALE (ponte) === scrive gli eventi anche in un file nella cartella Common,
// che il chatbot sulla STESSA macchina legge direttamente (senza key, senza server).
// Per i clienti remoti questa via non arriva: la' conta il push HTTP (con la key).
int _pp_log = -1;

void PappLogOpen(string fname)
{
   if(StringLen(fname) == 0 || MQLInfoInteger(MQL_TESTER)) return;
   _pp_log = FileOpen(fname, FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON|
                              FILE_SHARE_READ|FILE_SHARE_WRITE);
   if(_pp_log >= 0){ FileSeek(_pp_log, 0, SEEK_END);
      Print("PHAI: log locale aperto in Common\\Files\\", fname); }
   else Print("PHAI: log locale non aperto: ", fname);
}
void PappLogClose(){ if(_pp_log >= 0){ FileClose(_pp_log); _pp_log = -1; } }

void PappLogLine(string jsonline)   // scrive una linea {..} nel log locale (se aperto)
{
   if(_pp_log < 0) return;
   FileSeek(_pp_log, 0, SEEK_END);
   FileWriteString(_pp_log, jsonline + "\n");
   FileFlush(_pp_log);
}

// SEGNALE di trade (apertura/chiusura). dir: 1=BUY, 2=SELL.
void PappSignal(string action, string symbol, int dir, double entry, double sl, double tp,
                double lot, double exitPrice, double pnl, string reason)
{
   string j = StringFormat("\"t\":%d,\"symbol\":\"%s\",\"action\":\"%s\",\"dir\":%d,\"reason\":\"%s\"",
              (int)TimeCurrent(), symbol, action, dir, PappEsc(reason));
   if(entry > 0)     j += StringFormat(",\"entry\":%.5f", entry);
   if(sl > 0)        j += StringFormat(",\"sl\":%.5f", sl);
   if(tp > 0)        j += StringFormat(",\"tp\":%.5f", tp);
   if(lot > 0)       j += StringFormat(",\"lot\":%.2f", lot);
   if(exitPrice > 0) j += StringFormat(",\"exitPrice\":%.5f", exitPrice);
   j += StringFormat(",\"pnl\":%.1f", pnl);
   PappLogLine("{" + j + "}");   // ponte locale (owner, senza key)
   PappEvent(j);                 // push HTTP (clienti remoti, con key)
}

// VALIDAZIONE LICENZA (kill-switch server + grazia). Ritorna true se l'EA puo' aprire
// nuove posizioni su QUESTO simbolo per QUESTA key. Logica:
//  - server off / tester        -> true (opera con gli input locali)
//  - key mancante               -> false
//  - server risponde            -> g = (ok==1 && enabled!=0); aggiorna grazia; logga piano/rischio
//  - server irraggiungibile     -> GRAZIA: mantieni l'ultimo stato finche' l'ultimo contatto valido
//                                  e' entro _pp_grace; oltre -> false (anti-abuso).
datetime _pp_last_ok = 0;
int      _pp_grace   = 604800;  // 7 giorni di grazia se il server e' irraggiungibile
string   _pp_plan    = "";      // ultimo piano riportato dal server
double   _pp_risk    = 0;       // ultimo rischio% riportato dal server (informativo)
bool     _pp_enabled = true;    // kill-switch server per il simbolo

bool PappValidate(string symbol, string account, string broker="")
{
   if(!_pp_use || MQLInfoInteger(MQL_TESTER)){ _pp_enabled=true; return true; }
   if(StringLen(_pp_key) == 0){ Print("PHAI: license key mancante negli input."); return false; }
   string body = "{\"key\":\"" + PappEsc(_pp_key) + "\",\"account\":\"" + account +
                 "\",\"broker\":\"" + PappEsc(broker) + "\",\"symbol\":\"" + symbol + "\"}";
   string resp = PappPost("/api/ea/validate", body);
   if(resp == "")   // server irraggiungibile: grazia a tempo
   {
      bool g = (_pp_last_ok > 0 && (TimeCurrent() - _pp_last_ok) <= _pp_grace);
      if(!g) Print("PHAI: server irraggiungibile da >", _pp_grace/86400, " giorni: licenza in pausa.");
      else   Print("PHAI: server non raggiungibile, mantengo lo stato licenza (grazia).");
      return g;
   }
   bool ok      = (PappKv(resp, "ok") == "1");
   bool enabled = (PappKv(resp, "enabled") != "0");
   _pp_enabled  = enabled;
   _pp_plan     = PappKv(resp, "plan");
   string rs    = PappKv(resp, "risk"); _pp_risk = (StringLen(rs)>0)? StringToDouble(rs) : 0;
   bool licensed = ok && enabled;
   if(licensed) _pp_last_ok = TimeCurrent();   // contatto valido: resetta la grazia
   if(!ok)           Print("PHAI: LICENZA NON VALIDA (", PappKv(resp,"reason"), "). Nessuna nuova operazione.");
   else if(!enabled) Print("PHAI: strategia disattivata dal server per ", symbol, ". Nessuna nuova operazione.");
   else              Print("PHAI: licenza OK (piano ", _pp_plan, ", rischio ", rs, "%).");
   return licensed;
}

// FEATURE di mercato lette da PaPP_Median (Volatilità/Cluster/… + distanze dalle medie).
void PappFeatures(string symbol, double close, double d_med, double d_ma30, double d_ma365,
                  double cluster, double velocity, double accel, double volatility,
                  double order_score, double spread)
{
   string j = StringFormat(
      "\"t\":%d,\"symbol\":\"%s\",\"action\":\"features\",\"close\":%.5f,"
      "\"d_med\":%.3f,\"d_ma30\":%.3f,\"d_ma365\":%.3f,\"cluster\":%.3f,\"velocity\":%.3f,"
      "\"accel\":%.3f,\"volatility\":%.3f,\"order_score\":%.3f,\"spread\":%.3f",
      (int)TimeCurrent(), symbol, close, d_med, d_ma30, d_ma365, cluster, velocity,
      accel, volatility, order_score, spread);
   PappEvent(j);
}

// SNAPSHOT CONTO (balance/equity/margine + P&L delle posizioni del simbolo). Locale + HTTP.
void PappAccount(string symbol)
{
   double bal=AccountInfoDouble(ACCOUNT_BALANCE), eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double mrg=AccountInfoDouble(ACCOUNT_MARGIN), fm=AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double ml=AccountInfoDouble(ACCOUNT_MARGIN_LEVEL), prof=AccountInfoDouble(ACCOUNT_PROFIT);
   double symProf=0; int symOpen=0;
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=symbol) continue;
      symProf+=PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP); symOpen++; }
   double symPct=(bal>0)? symProf/bal*100.0 : 0.0;
   string j=StringFormat("\"t\":%d,\"symbol\":\"%s\",\"action\":\"account\",\"balance\":%.2f,\"equity\":%.2f,"
      "\"margin\":%.2f,\"free_margin\":%.2f,\"margin_level\":%.2f,\"profit\":%.2f,"
      "\"sym_profit\":%.2f,\"sym_pct\":%.2f,\"sym_open\":%d",
      (int)TimeCurrent(),symbol,bal,eq,mrg,fm,ml,prof,symProf,symPct,symOpen);
   PappLogLine("{"+j+"}"); PappEvent(j);
}

// STATO strategia: oscillatore (0-100) + nota "dove siamo". Locale + HTTP.
void PappState(string symbol, double osc, string info)
{
   string j=StringFormat("\"t\":%d,\"symbol\":\"%s\",\"action\":\"state\",\"osc\":%.1f,\"info\":\"%s\"",
      (int)TimeCurrent(),symbol,osc,PappEsc(info));
   PappLogLine("{"+j+"}"); PappEvent(j);
}

// STATO strategia REVERSIONE con metriche dedicate: distanza dalla media (%),
// volatilita' del cross (%), quanti punti oscillatore mancano al BUY/SELL, barre
// consecutive in banda estrema. Locale + HTTP.
void PappRelval(string symbol, double osc, double dist, double vol,
                double toBuy, double toSell, int barsOut, string info)
{
   string j=StringFormat("\"t\":%d,\"symbol\":\"%s\",\"action\":\"state\",\"osc\":%.1f,"
      "\"dist\":%.4f,\"vol\":%.4f,\"to_buy\":%.1f,\"to_sell\":%.1f,\"bars_out\":%d,\"info\":\"%s\"",
      (int)TimeCurrent(),symbol,osc,dist,vol,toBuy,toSell,barsOut,PappEsc(info));
   PappLogLine("{"+j+"}"); PappEvent(j);
}

// BARRE OHLC del cross per il grafico navigabile (di solito D1). Invia le ultime
// `count` barre (dalla piu' vecchia alla piu' recente). Lato server sono GLOBALI per
// simbolo. Locale (ponte) + HTTP. Chiamare con count alto all'avvio (backfill) e
// count basso ad ogni nuova barra (aggiornamento).
void PappBars(string symbol, ENUM_TIMEFRAMES tf, int count)
{
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int n = CopyRates(symbol, tf, 0, count, r);
   if(n <= 0) return;
   string arr = "";
   for(int i = n-1; i >= 0; i--)
   {
      if(arr != "") arr += ",";
      arr += StringFormat("{\"t\":%d,\"o\":%.5f,\"h\":%.5f,\"l\":%.5f,\"c\":%.5f}",
             (int)r[i].time, r[i].open, r[i].high, r[i].low, r[i].close);
   }
   string j = StringFormat("\"symbol\":\"%s\",\"action\":\"bars\",\"bars\":[%s]", symbol, arr);
   PappLogLine("{" + j + "}");   // ponte locale (owner)
   PappEvent(j);                 // HTTP (clienti con key)
}

#endif
