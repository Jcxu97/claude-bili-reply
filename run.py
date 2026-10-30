# One automated reply round, plus helper commands. Usage: python run.py check|init|fetch|round|post FILE
import json, os, shutil, subprocess, sys, time
from pathlib import Path
import bili

ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'state'
SEEN = STATE / 'seen.json'
VIDEOS = json.loads((ROOT / 'videos.json').read_text(encoding='utf-8'))
LOG = STATE / 'log.md'
BAD = ('—', '–')
for d in ('inbox', 'out', 'runs'):
    (STATE / d).mkdir(parents=True, exist_ok=True)


def now():
    return time.strftime('%Y%m%d-%H%M%S')


def load_seen():
    return set(json.loads(SEEN.read_text(encoding='utf-8'))) if SEEN.exists() else set()


def save_seen(s):
    SEEN.write_text(json.dumps(sorted(s)), encoding='utf-8')


def log(text):
    with LOG.open('a', encoding='utf-8') as f:
        f.write(text + '\n')


def pull():
    """Every comment on every listed video, with the video id attached."""
    rows = []
    for v in VIDEOS:
        try:
            for r in bili.comments(v['aid']):
                r['ep'] = v['ep']
                rows.append(r)
        except Exception as e:
            log('- %s fetch %s failed: %s' % (now(), v['ep'], e))
        time.sleep(1)
    return rows


def new_items(rows, seen):
    by = {r['rpid']: r for r in rows}
    items = []
    for r in sorted(rows, key=lambda r: r['ctime']):
        if r['rpid'] in seen or r['mid'] == bili.OWNER:
            continue
        thread = [x for x in rows if x['root'] == r['root']]
        ctx = {'root': by.get(r['root'], {}).get('msg') if r['root'] != r['rpid'] else None,
               'parent': by.get(r['parent'], {}).get('msg') if r['parent'] not in ('0', r['root']) else None,
               'thread': [{'rpid': x['rpid'], 'user': x['user'], 'owner': x['mid'] == bili.OWNER, 'msg': x['msg']}
                          for x in sorted(thread, key=lambda x: x['ctime'])][-12:]}
        items.append(dict(r, context=ctx))
    return items


def post(items, out):
    """Post the replies Claude wrote. Returns the rpids it handled."""
    by = {i['rpid']: i for i in items}
    done = set()
    for o in out:
        it = by.get(str(o.get('rpid')))
        act = o.get('action')
        if not it:
            log('  - skip unknown rpid %s' % o.get('rpid'))
            continue
        done.add(it['rpid'])
        if act == 'skip':
            log('  - skip %s %s: %s' % (it['ep'], it['user'], it['msg'][:40].replace('\n', ' ')))
            continue
        msg = (o.get('msg') or '').strip()
        if not msg or len(msg) > 1000 or any(b in msg for b in BAD):
            log('  - REJECT %s (empty, too long, or dash): %s' % (it['rpid'], msg[:60]))
            continue
        if o.get('old'):
            c, m = bili.delete(it['aid'], o['old'])
            log('  - delete old %s: %s %s' % (o['old'], c, m))
            time.sleep(3)
        c, m, rp = bili.reply(it['aid'], msg, it['root'], it['rpid'])
        o['sent'] = rp
        log('  - %s %s | Q %s | A %s | %s %s' % (it['ep'], it['user'], it['msg'][:60].replace('\n', ' '),
                                                msg.replace('\n', ' '), c, rp or m))
        time.sleep(6)
    return done


def ask_claude(stamp):
    cfg = bili.CFG.get('agent', {})
    env = dict(os.environ)
    agent_env = ROOT / 'agent.env'
    if agent_env.exists():
        env.update(json.loads(agent_env.read_text(encoding='utf-8')))
    prompt = ('读 PLAYBOOK.md,按里面的流程处理 state/inbox/%s.json 里的每一条评论,'
              '把结果写进 state/out/%s.json。只写这一个输出文件和 PLAYBOOK 允许的笔记文件,不要联网、不要发评论。' % (stamp, stamp))
    exe = shutil.which('claude', path=env.get('PATH')) or 'claude'
    cmd = [exe, '-p', '--model', cfg.get('model', 'opus'), '--effort', cfg.get('effort', 'high'),
           '--permission-mode', 'default', '--allowedTools', 'Read Grep Glob Write Edit Bash',
           '--disallowedTools', 'WebFetch WebSearch Agent', '--output-format', 'stream-json', '--verbose']
    # Stream every event to runs/<stamp>.jsonl so the web page can show what Claude is doing right now.
    deadline = time.time() + int(cfg.get('timeout_min', 45)) * 60
    result = {}
    p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
    p.stdin.write(prompt)
    p.stdin.close()
    with (STATE / 'runs' / (stamp + '.jsonl')).open('w', encoding='utf-8') as f:
        for line in p.stdout:
            f.write(line)
            f.flush()
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'result':
                result = ev
            elif ev.get('type') == 'assistant':
                for c in (ev.get('message') or {}).get('content') or []:
                    if c.get('type') == 'tool_use':
                        status('claude', stamp, tool='%s %s' % (c['name'], json.dumps(c.get('input'), ensure_ascii=False)[:160]))
            if time.time() > deadline:
                p.kill()
                break
    p.wait()
    return p.returncode, result


def status(stage, stamp=None, **kw):
    (STATE / 'status.json').write_text(json.dumps(dict(kw, stage=stage, stamp=stamp, t=int(time.time())),
                                                  ensure_ascii=False), encoding='utf-8')


def record(entry):
    f = STATE / 'rounds.json'
    rounds = json.loads(f.read_text(encoding='utf-8-sig')) if f.exists() else []
    rounds.append(entry)
    f.write_text(json.dumps(rounds[-500:], ensure_ascii=False, indent=1), encoding='utf-8')


def git_commit(stamp):
    if (ROOT / '.git').exists():
        subprocess.run(['git', 'add', '-A'], cwd=ROOT, capture_output=True)
        subprocess.run(['git', 'commit', '-qm', 'round ' + stamp], cwd=ROOT, capture_output=True)


def cmd_round():
    lock = STATE / 'round.lock'
    if lock.exists() and time.time() - lock.stat().st_mtime < 3600:
        return
    lock.write_text(str(os.getpid()))
    t0, stamp, entry = time.time(), now(), None
    try:
        status('fetch', stamp)
        ok, name, _ = bili.nav()
        if not ok:
            log('- %s 登录失效,cookie 要更新(见 README)' % stamp)
            entry = {'stamp': stamp, 'result': 'login_failed'}
            return
        seen = load_seen()
        items = new_items(pull(), seen)
        if not items:
            entry = {'stamp': stamp, 'result': 'no_new', 'sec': int(time.time() - t0)}
            return
        inbox = STATE / 'inbox' / (stamp + '.json')
        inbox.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding='utf-8')
        log('- %s %d 条新评论' % (stamp, len(items)))
        status('claude', stamp, n=len(items))
        rc, res = ask_claude(stamp)
        u = res.get('usage') or {}
        entry = {'stamp': stamp, 'new': len(items), 'rc': rc, 'turns': res.get('num_turns'),
                 'usage': {k: u.get(k) for k in ('input_tokens', 'cache_read_input_tokens',
                                                 'cache_creation_input_tokens', 'output_tokens')},
                 'cost': res.get('total_cost_usd')}
        outf = STATE / 'out' / (stamp + '.json')
        if not outf.exists():
            log('  - claude 没写输出 (rc %s),下一轮重试' % rc)
            entry['result'] = 'no_output'
            return
        status('post', stamp, n=len(items))
        out = json.loads(outf.read_text(encoding='utf-8'))
        done = post(items, out)
        outf.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        save_seen(seen | done)
        entry.update(result='ok', replied=sum(1 for o in out if o.get('sent')),
                     skipped=sum(1 for o in out if o.get('action') == 'skip'))
        log('  - 用量 %s' % json.dumps(entry['usage']))
    except Exception as e:
        log('  - %s 出错 %r' % (stamp, e))
        entry = dict(entry or {'stamp': stamp}, result='error', error=repr(e)[:300])
    finally:
        if entry:
            entry['sec'] = int(time.time() - t0)
            record(entry)
        status('idle', stamp)
        git_commit(stamp)
        lock.unlink(missing_ok=True)


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else 'round'
    if c == 'check':
        print(bili.nav())
    elif c == 'init':
        # Optional arg: unix time. Only comments up to it are marked, newer ones stay for the next round.
        cut = int(sys.argv[2]) if len(sys.argv) > 2 else int(time.time())
        rows = [r for r in pull() if r['ctime'] <= cut]
        save_seen(load_seen() | {r['rpid'] for r in rows})
        print('marked', len(rows))
    elif c == 'fetch':
        for i in new_items(pull(), load_seen()):
            print(json.dumps({k: i[k] for k in ('ep', 'rpid', 'user', 'msg')}, ensure_ascii=False))
    elif c == 'round':
        cmd_round()
    elif c == 'post':
        f = Path(sys.argv[2])
        rows = pull()
        items = new_items(rows, set())
        out = json.loads(f.read_text(encoding='utf-8'))
        save_seen(load_seen() | post(items, out))
        f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
