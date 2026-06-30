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
   PappEvent(j);
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

#endif
