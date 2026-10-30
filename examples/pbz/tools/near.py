# Nearest bells (save points) to a world position, so a place can be described by the bell name players see.
# Usage: python tools/near.py X Y Z        or   python tools/near.py --map MeiGuHu   (list the bells of one map)
# Distances are in meters (world units / 100). Compare Z too: underground rooms sit far below the bell above them.
import json, math, sys
from pathlib import Path

G = Path(__file__).resolve().parent.parent / 'game'
L = json.loads((G / 'loc_zh-Hans.json').read_text(encoding='utf-8'))
B = json.loads((G / 'json/ProjectPBZ/Content/PBZContent/DataTable/UI/DT_BellData.json').read_text(encoding='utf-8'))[0]['Rows']
sys.stdout.reconfigure(encoding='utf-8')
if sys.argv[1] == '--map':
    for b in sorted(B.values(), key=lambda b: b['BellID']):
        if b['MapID'] == sys.argv[2]:
            l = b['BellLocation']
            print(b['BellID'], L.get('Default/' + b['BellID']), int(l['X']), int(l['Y']), int(l['Z']))
else:
    p = tuple(float(v) for v in sys.argv[1:4])
    for b in sorted(B.values(), key=lambda b: math.dist(p, tuple(b['BellLocation'][k] for k in 'XYZ')))[:6]:
        l = b['BellLocation']
        print(b['BellID'], L.get('Default/' + b['BellID']), b['MapID'], '%dm' % (math.dist(p, (l['X'], l['Y'], l['Z'])) / 100),
              'height diff %dm' % ((p[2] - l['Z']) / 100))
