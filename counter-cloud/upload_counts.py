"""Run beside the existing counter. Python standard library only."""
import getpass
import json
import os
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def main():
    url = os.environ.get('COUNTER_UPLOAD_URL', '').strip()
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path != '/api/upload' or parsed.query or parsed.fragment:
        raise SystemExit('COUNTER_UPLOAD_URL に https://送信先/api/upload を指定してください')
    token = os.environ.get('COUNTER_UPLOAD_TOKEN') or getpass.getpass('送信専用トークン（非表示）: ')
    if len(token) < 32:
        raise SystemExit('送信トークンは32文字以上必要です')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    print('[UPLOAD] 10秒間隔で人数を送信します。終了: Ctrl+C')
    while True:
        try:
            with opener.open('http://127.0.0.1:8000/api/counts', timeout=3) as r:
                d = json.loads(r.read(16385))
            # Explicit allowlist: never send camera credentials, images or tracker IDs.
            payload = {k: d[k] for k in ('date','enter','exit','current','status','last_frame','last_event','server_time')}
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), method='POST', headers={
                'Content-Type':'application/json', 'Authorization':'Bearer '+token})
            with opener.open(req, timeout=5) as r:
                result = json.loads(r.read(4096))
            print('[UPLOAD] 送信完了' if result.get('ok') else '[UPLOAD] 応答を確認してください', flush=True)
        except urllib.error.HTTPError as e:
            print(f'[UPLOAD] HTTP {e.code}。設定を確認してください。計測は継続します。', flush=True)
        except Exception as e:
            print(f'[UPLOAD] 送信待ち ({type(e).__name__})。次回、最新の累計値を再送します。', flush=True)
        time.sleep(10)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n[UPLOAD] 終了')
