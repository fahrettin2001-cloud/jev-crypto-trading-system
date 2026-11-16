"""Yalnızca yerel bilgisayardan okunabilen sanal hesap paneli."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from .reporting import account_report
from .storage import SQLitePortfolio

HTML = '''<!doctype html><html lang="tr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Jev · Sanal hesap</title>
<style>
body{margin:0;background:#101823;color:#e8edf4;font:16px system-ui}main{max-width:1100px;margin:50px auto;padding:24px}
h1{font-size:36px;margin:12px 0}small,.muted{color:#9eafc1}.badge{color:#66e0b3}section{background:#1a2636;border-radius:14px;padding:24px;margin:20px 0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px}.value{font-size:26px;margin-top:8px}
table{width:100%;border-collapse:collapse;text-align:left}td,th{padding:12px 8px;border-bottom:1px solid #304057}pre{white-space:pre-wrap;overflow-wrap:anywhere}
#error{color:#ffb4a9}a{color:#66e0b3}.scroll{overflow:auto}
</style><main><span class="badge">● Yalnızca sanal işlem</span><h1>Hesabına genel bakış</h1>
<p class="muted">Kayıtlı hesabın, pozisyonların ve işlem geçmişin. Bu panel yalnızca görüntüler.</p>
<p id="error" role="alert"></p><div class="cards" id="cards"></div>
<section><h2>Pozisyonlar</h2><div class="scroll"><table><thead><tr><th>Varlık</th><th>Miktar</th><th>Ortalama maliyet</th></tr></thead><tbody id="positions"></tbody></table></div></section>
<section><h2>Risk politikası</h2><p id="policy-state"></p><div id="policy"></div></section>
<section><h2>İşlem geçmişi</h2><div class="scroll"><table><thead><tr><th>Zaman</th><th>Varlık</th><th>Yön</th><th>Miktar</th><th>Fiyat</th><th>Komisyon</th></tr></thead><tbody id="history"></tbody></table></div></section>
<small id="updated"></small></main><script>
const el=id=>document.getElementById(id);
function cell(row,text){const c=document.createElement('td');c.textContent=text;row.appendChild(c)}
async function refresh(){try{
const [r,h]=await Promise.all([fetch('/api/status'),fetch('/api/history')]);
if(!r.ok||!h.ok)throw new Error('Hesap okunamadı. Dosyayı ve sunucu kaydını kontrol et.');
const s=await r.json(),trades=await h.json();el('error').textContent='';el('cards').replaceChildren();
for(const [title,value] of [['Nakit',s.cash+' '+s.quote],['Gerçekleşen K/Z',s.realized_pnl],['Toplam komisyon',s.total_fees],['İşlem sayısı',s.trade_count]]){
const box=document.createElement('section'),label=document.createElement('div'),v=document.createElement('div');label.textContent=title;v.textContent=value;v.className='value';box.append(label,v);el('cards').append(box)}
el('positions').replaceChildren();for(const [symbol,p]of Object.entries(s.positions)){const row=document.createElement('tr');[symbol,p.quantity,p.avg_cost].forEach(t=>cell(row,t));el('positions').append(row)}
el('policy-state').textContent=s.policy.error||'Kayıtlı politika · sürüm '+s.policy.version;el('policy').replaceChildren();
if(s.policy.limits){for(const [key,label]of [['max_trade_notional','İşlem tutarı üst sınırı'],['min_cash_reserve','Korunacak asgari nakit'],['max_position_notional','Tek varlıkta pozisyon sınırı'],['max_total_position_notional','Toplam pozisyon sınırı'],['max_daily_realized_loss','Günlük gerçekleşen zarar sınırı'],['max_price_age_seconds','Fiyat yaşı sınırı (saniye)'],['allowed_symbols','İzin verilen varlıklar']]){const line=document.createElement('p');const value=s.policy.limits[key];line.textContent=label+': '+(value===null?'Tanımlanmadı':Array.isArray(value)?value.join(', ')||'Hiçbiri':value);el('policy').append(line)}}else{el('policy').textContent='İşlem için politika tanımlanmalı.'}
el('history').replaceChildren();for(const t of trades.slice().reverse()){const row=document.createElement('tr');[t.timestamp,t.symbol,t.side,t.quantity,t.price,t.fee].forEach(v=>cell(row,v));el('history').append(row)}
el('updated').textContent='Son yenileme: '+new Date().toLocaleTimeString('tr-TR');
}catch(e){el('error').textContent=e.message}}
refresh();setInterval(refresh,10000);
</script></html>'''


def make_server(path, port=8765):
    path = Path(path)
    # Eksik/uyumsuz hesapla sunucu başlatma.
    with SQLitePortfolio.open(path):
        pass

    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, body, content_type='application/json; charset=utf-8'):
            encoded = body.encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(encoded)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if self.headers.get('Host') not in allowed:
                self.reply(403, '{"error":"Yerel erişim gerekli"}')
                return
            route = urlsplit(self.path).path
            if route == '/':
                self.reply(200, HTML, 'text/html; charset=utf-8')
                return
            if route not in ('/api/status', '/api/history'):
                self.reply(404, '{"error":"Bulunamadı"}')
                return
            try:
                with SQLitePortfolio.open(path) as account:
                    if route == '/api/status':
                        data = account_report(account)
                    else:
                        data = [{'timestamp':t.timestamp.isoformat(), 'symbol':t.symbol,
                                 'side':t.side, 'quantity':str(t.quantity), 'price':str(t.price),
                                 'fee':str(t.fee)} for t in account.portfolio.trades]
                self.reply(200, json.dumps(data, ensure_ascii=False))
            except (ValueError, TypeError, sqlite3.Error):
                self.reply(500, '{"error":"Hesap okunamadı"}')

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='Yerel sanal hesap paneli (salt okunur)')
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    try:
        server = make_server(args.db, args.port)
        print(f'Yerel sanal hesap paneli, port {server.server_port}. Durdurmak için Ctrl+C.', flush=True)
        with server:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        parser.exit(1, f'Hata: {exc}\n')


if __name__ == '__main__':
    main()
