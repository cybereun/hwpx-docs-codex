"""hd chart: make or inspect native charts.

  hd chart make <chart.json> <out.hwpx>   a document with that chart spec (a chart dict, or {"chart": {...}} blocks)
  hd chart dump <in.hwpx>                 every native chart of the file as a spec, one JSON per line
Prints `HWPX WRITTEN <path>` or `CHART <n> <type> <series> series` lines.
"""
from ..core import tmpdir
import json
import os
import sys


def main(argv):
    if len(argv) >= 3 and argv[0] == 'make':
        from ..core import build
        c = json.load(open(argv[1], encoding='utf-8'))
        body = c if isinstance(c, list) else [c if 'chart' in c else {'chart': dict(c, native=True)}]
        print('HWPX WRITTEN', build.write({'body': body}, argv[2], os.path.dirname(os.path.abspath(argv[1]))))
        return 0
    if len(argv) >= 2 and argv[0] == 'dump':
        from ..core import read
        spec = read.read(argv[1], os.path.join(tmpdir.mkdtemp('hd_chart_'), 'dump.json'))
        secs = spec.get('sections') or [spec]
        n = 0
        for s in secs:
            for b in s.get('body', []):
                if isinstance(b, dict) and isinstance(b.get('chart'), dict) and b['chart'].get('native'):
                    n += 1
                    c = b['chart']
                    print('CHART', n, c.get('type', 'ooxml'), len(c.get('series', [])), 'series')
                    print(json.dumps(c, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
