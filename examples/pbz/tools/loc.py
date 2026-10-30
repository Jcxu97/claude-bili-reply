# Search the Chinese game text. Usage: python tools/loc.py WORD [WORD...]   (all words must match; a word can be part of a key)
# python tools/loc.py --key Dlg_DHSD_HuXinWeiWan   prints entries whose key contains the text
import json, sys
from pathlib import Path

L = json.loads((Path(__file__).resolve().parent.parent / 'game' / 'loc_zh-Hans.json').read_text(encoding='utf-8'))
sys.stdout.reconfigure(encoding='utf-8')
args = sys.argv[1:]
if args and args[0] == '--key':
    for k, v in L.items():
        if args[1] in k:
            print(k, '=', v.replace('\n', ' / '))
else:
    n = 0
    for k, v in L.items():
        if all(w in v or w in k for w in args):
            print(k, '=', v.replace('\n', ' / ')[:300])
            n += 1
            if n >= 80:
                print('... more, add words to narrow')
                break
