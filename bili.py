# B站 API with the owner's cookies. Standard library only. Cookies come from config.toml [bili].
import json, time, tomllib, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG = tomllib.loads((ROOT / 'config.toml').read_text(encoding='utf-8'))
CK = CFG['bili']
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'
# The server sets HTTPS_PROXY for other jobs. B站 is domestic, so skip the proxy.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
COOKIE = '; '.join('%s=%s' % (k, v) for k, v in CK.items() if k in
                   ('SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5', 'buvid3', 'buvid4', 'sid'))
OWNER = int(CK['DedeUserID'])


def call(url, data=None, host='https://api.bilibili.com'):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(host + url, data=body, headers={
        'User-Agent': UA, 'Cookie': COOKIE, 'Referer': 'https://www.bilibili.com/', 'Origin': 'https://www.bilibili.com'})
    for i in range(3):
        try:
            with OPENER.open(req, timeout=20) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception:
            if i == 2:
                raise
            time.sleep(3)


def _row(c, aid, root=None):
    return {'aid': aid, 'rpid': c['rpid_str'], 'root': root or c['rpid_str'], 'parent': c.get('parent_str', '0'),
            'mid': c['mid'], 'user': c['member']['uname'], 'ctime': c['ctime'], 'like': c.get('like', 0),
            'msg': c['content']['message']}


def comments(aid, pages=5):
    """All comments of a video with their nested replies, flat."""
    out = []
    for pn in range(1, pages + 1):
        d = call('/x/v2/reply?type=1&sort=0&ps=20&pn=%d&oid=%s' % (pn, aid)).get('data') or {}
        rs = d.get('replies') or []
        for c in rs:
            out.append(_row(c, aid))
            if c.get('rcount', 0) > 0:
                for sp in range(1, 6):
                    s = call('/x/v2/reply/reply?type=1&ps=20&pn=%d&oid=%s&root=%s' % (sp, aid, c['rpid_str'])).get('data') or {}
                    ss = s.get('replies') or []
                    out.extend(_row(x, aid, c['rpid_str']) for x in ss)
                    if len(ss) < 20:
                        break
                    time.sleep(0.5)
        if len(rs) < 20:
            break
        time.sleep(0.5)
    return out


def reply(aid, msg, root, parent):
    j = call('/x/v2/reply/add', {'type': 1, 'oid': aid, 'root': root, 'parent': parent, 'message': msg,
                                 'plat': 1, 'csrf': CK['bili_jct']})
    return j['code'], j.get('message'), (j.get('data') or {}).get('rpid_str')


def delete(aid, rpid):
    j = call('/x/v2/reply/del', {'type': 1, 'oid': aid, 'rpid': rpid, 'csrf': CK['bili_jct']})
    return j['code'], j.get('message')


def dm(mid, text):
    import uuid
    j = call('/web_im/v1/web_im/send_msg', {
        'msg[sender_uid]': OWNER, 'msg[receiver_type]': 1, 'msg[receiver_id]': mid, 'msg[msg_type]': 1,
        'msg[msg_status]': 0, 'msg[dev_id]': str(uuid.uuid4()).upper(), 'msg[timestamp]': int(time.time()),
        'msg[content]': json.dumps({'content': text}, ensure_ascii=False),
        'csrf': CK['bili_jct'], 'csrf_token': CK['bili_jct']}, host='https://api.vc.bilibili.com')
    return j['code'], j.get('message')


def nav():
    d = call('/x/web-interface/nav').get('data') or {}
    return d.get('isLogin'), d.get('uname'), d.get('mid')
