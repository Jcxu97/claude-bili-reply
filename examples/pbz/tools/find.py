# List the exported files that mention a word (item ID, tag, flow name, Chinese tag). Usage: python tools/find.py WORD [AREA]
# AREA is one of flowgraph, actordata, json, js, map (default: all). Prints the file path and how many times it hits.
import sys
from pathlib import Path

G = Path(__file__).resolve().parent.parent / 'game'
sys.stdout.reconfigure(encoding='utf-8')
word = sys.argv[1]
areas = [sys.argv[2]] if len(sys.argv) > 2 else ['flowgraph', 'json', 'map', 'js', 'actordata']
for a in areas:
    for f in sorted((G / a).rglob('*')):
        if f.is_file() and f.suffix in ('.json', '.js'):
            n = f.read_text(encoding='utf-8', errors='ignore').count(word)
            if n:
                print(n, f.relative_to(G).as_posix())
