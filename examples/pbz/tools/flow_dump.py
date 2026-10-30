# Print an exported flow graph json as a tree from its Start node. Arg: json path.
import json, re, sys
ex = json.load(open(sys.argv[1], encoding='utf-8'))
nodes = {e['Properties']['NodeGuid']: e for e in ex if isinstance(e.get('Properties'), dict) and 'NodeGuid' in e['Properties']}
SKIP = {'GraphNode', 'NodeGuid', 'Connections', 'EditorInputConnectionNodesGuids', 'InputPins', 'OutputPins'}


def brief(e):
    p = e['Properties']
    bits = []
    for k, v in p.items():
        if k in SKIP:
            continue
        s = json.dumps(v, ensure_ascii=False)
        s = re.sub(r'"ObjectName": "[^"]*?\'([^\'"]+)\'"', r'\1', s)
        s = re.sub(r', "ObjectPath": "[^"]*"', '', s)
        bits.append('%s=%s' % (k, s[:120]))
    return e['Type'].replace('FlowNode_', '').replace('PBZFlow', '') + ' ' + ' '.join(bits)


seen = set()


def walk(g, depth, via):
    e = nodes.get(g)
    if not e:
        return
    tag = '[%s] ' % via if via else ''
    if g in seen:
        print('  ' * depth + tag + '(again) ' + e['Name'])
        return
    seen.add(g)
    print('  ' * depth + tag + brief(e)[:400])
    for c in e['Properties'].get('Connections', []):
        walk(c['Value']['NodeGuid'], depth + 1, c['Key'])


for g, e in nodes.items():
    if e['Type'] == 'FlowNode_Start':
        walk(g, 0, '')
for g, e in nodes.items():
    if g not in seen and not e['Properties'].get('EditorInputConnectionNodesGuids'):
        walk(g, 0, 'entry')
