# Status page for the reply automation. Usage: python web.py [host] [port]   (default 127.0.0.1 8789)
import json, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
TASK = 'bili-reply'
STATE = ROOT / 'state'
VIDEOS = {v['ep']: v for v in json.loads((ROOT / 'videos.json').read_text(encoding='utf-8'))}
CACHE = {}


def cached(key, sec, fn):
    hit = CACHE.get(key)
    if hit and time.time() - hit[0] < sec:
        return hit[1]
    try:
        val = fn()
    except Exception as e:
        val = {'error': repr(e)[:200]}
    CACHE[key] = (time.time(), val)
    return val


def rj(p, default):
    try:
        return json.loads(p.read_text(encoding='utf-8-sig'))
    except Exception:
        return default


def task_info():
    ps = ("$i = Get-ScheduledTask -TaskName %s | Get-ScheduledTaskInfo; "
          "@{next=$i.NextRunTime.ToString('yyyy-MM-dd HH:mm'); last=$i.LastRunTime.ToString('yyyy-MM-dd HH:mm'); "
          "code=$i.LastTaskResult; state=(Get-ScheduledTask -TaskName %s).State.ToString()} | ConvertTo-Json") % (TASK, TASK)
    out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=20).stdout
    return json.loads(out)


def login():
    sys.path.insert(0, str(ROOT))
    import bili
    ok, name, mid = bili.nav()
    return {'ok': bool(ok), 'name': name}


def round_detail(stamp):
    items = rj(STATE / 'inbox' / (stamp + '.json'), [])
    out = {str(o.get('rpid')): o for o in rj(STATE / 'out' / (stamp + '.json'), [])}
    rows = []
    for i in items:
        o = out.get(i['rpid'], {})
        rows.append({'ep': i['ep'], 'title': (VIDEOS.get(i['ep']) or {}).get('title', ''), 'bvid': (VIDEOS.get(i['ep']) or {}).get('bvid'),
                     'user': i['user'], 'q': i['msg'], 'action': o.get('action', '待处理'), 'a': o.get('msg') or o.get('why') or '',
                     'sent': o.get('sent'), 'source': o.get('source', ''), 'rpid': i['rpid'], 'root': i['root']})
    tools, summary = [], ''
    f = STATE / 'runs' / (stamp + '.jsonl')
    if f.exists():
        for line in f.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'assistant':
                for c in (ev.get('message') or {}).get('content') or []:
                    if c.get('type') == 'tool_use':
                        tools.append('%s %s' % (c['name'], json.dumps(c.get('input'), ensure_ascii=False)[:200]))
            elif ev.get('type') == 'result':
                summary = ev.get('result') or ''
    return {'stamp': stamp, 'rows': rows, 'tools': tools, 'summary': summary}


def api():
    st = rj(STATE / 'status.json', {'stage': 'idle'})
    rounds = rj(STATE / 'rounds.json', [])
    work = [r for r in rounds if r.get('new')]
    today = time.strftime('%Y%m%d')
    tok = lambda r: sum(v or 0 for v in (r.get('usage') or {}).values())
    latest = st.get('stamp') if st.get('stage') != 'idle' else (work[-1]['stamp'] if work else None)
    return {'status': st, 'now': int(time.time()), 'task': cached('task', 30, task_info), 'login': cached('login', 600, login),
            'rounds': rounds[-60:][::-1],
            'today': {'rounds': sum(1 for r in work if r['stamp'].startswith(today)),
                      'replied': sum(r.get('replied') or 0 for r in work if r['stamp'].startswith(today)),
                      'skipped': sum(r.get('skipped') or 0 for r in work if r['stamp'].startswith(today)),
                      'tokens': sum(tok(r) for r in work if r['stamp'].startswith(today))},
            'latest': round_detail(latest) if latest else None,
            'log': (STATE / 'log.md').read_text(encoding='utf-8').splitlines()[-40:] if (STATE / 'log.md').exists() else []}


def run_now():
    lock = STATE / 'round.lock'
    if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
        return {'ok': False, 'msg': '这一轮还在跑'}
    r = subprocess.run(['powershell', '-NoProfile', '-Command', 'Start-ScheduledTask -TaskName ' + TASK],
                       capture_output=True, text=True, timeout=20)
    CACHE.pop('task', None)
    return {'ok': r.returncode == 0, 'msg': '已开始' if r.returncode == 0 else (r.stderr or r.stdout)[:200]}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype):
        b = body.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if urlparse(self.path).path == '/api/run':
            return self.send(json.dumps(run_now(), ensure_ascii=False), 'application/json')
        self.send('{}', 'application/json')

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == '/api':
            self.send(json.dumps(api(), ensure_ascii=False), 'application/json')
        elif u.path == '/api/round':
            stamp = parse_qs(u.query).get('stamp', [''])[0]
            if not (len(stamp) == 15 and stamp.replace('-', '').isdigit()):
                return self.send('{}', 'application/json')
            self.send(json.dumps(round_detail(stamp), ensure_ascii=False), 'application/json')
        else:
            self.send((ROOT / 'web.html').read_text(encoding='utf-8'), 'text/html')


if __name__ == '__main__':
    host = sys.argv[1] if len(sys.argv) > 1 else '127.0.0.1'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8789
    # On Windows SO_REUSEADDR lets a second copy bind the same port without an error, so turn it off.
    ThreadingHTTPServer.allow_reuse_address = False
    ThreadingHTTPServer((host, port), H).serve_forever()
