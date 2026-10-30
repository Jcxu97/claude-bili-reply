# Print a quest asset: each step with its text, map, auto-track flag and BlockTags (a BlockTag is a deadline:
# once that tag is set, the step or the whole quest closes). Usage: python tools/quest.py HuXinMiMi
import json, sys
from pathlib import Path

G = Path(__file__).resolve().parent.parent / 'game'
L = json.loads((G / 'loc_zh-Hans.json').read_text(encoding='utf-8'))
sys.stdout.reconfigure(encoding='utf-8')
hits = list((G / 'flowgraph/ProjectPBZ/Content/PBZstory/PBZQuest').rglob(sys.argv[1] + '.json'))
for f in hits:
    print('==', f.relative_to(G).as_posix())
    for e in json.loads(f.read_text(encoding='utf-8')):
        p = e.get('Properties') or {}
        if e.get('Type') == 'PBZQuestBranch':
            key = (p.get('FlowLocTarget') or {}).get('Key')
            print('step', p.get('ID'), L.get('Default/%s' % key, key), '| map', p.get('BelongToWorld') or p.get('AcceptBelongToWorld'),
                  '| autotrack', p.get('bAllowAutoTrack', True), '| block', p.get('BlockTags'), '| loc', p.get('Location'))
        elif e.get('Name', '').startswith('Default__'):
            print('quest', L.get('Default/%s' % (p.get('FlowLocTextQuestName') or {}).get('Key')), '| type', p.get('QuestType'),
                  '| quest BlockTags', p.get('BlockTags'))
        elif e.get('Type', '').startswith('BPT_') and p:
            print('   task', e.get('Outer', {}).get('ObjectName', '')[-30:], json.dumps(p, ensure_ascii=False)[:200])
