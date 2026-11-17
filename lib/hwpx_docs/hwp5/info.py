"""`hd hwp info <in.hwp>`: version, FileHeader flags, streams, and per section the paragraphs, tables and objects."""
import sys
from collections import Counter

from . import fmt

FLAG_NAMES = {0x1: 'compressed', 0x2: 'password', 0x4: 'distribution', 0x8: 'script', 0x10: 'DRM',
              0x20: 'XML template', 0x40: 'history', 0x80: 'signature', 0x100: 'certificate encryption',
              0x400: 'certificate DRM', 0x800: 'CCL', 0x1000: 'mobile', 0x2000: 'private information security',
              0x4000: 'track changes', 0x8000: 'KOGL'}


def info(path, out=print):
    pk = fmt.Package(path)
    out(f'HWP {pk.version_text()} {path}')
    out('FLAGS ' + (', '.join(n for b, n in FLAG_NAMES.items() if pk.flags & b) or 'none'))
    for p, e in sorted(pk.streams.items()):
        out(f'STREAM {p} {len(e.data)}')
    for s in pk.sections:
        recs = pk.records(s)
        paras = fmt.paragraphs(recs)
        kinds = Counter(p.kind for p in paras)
        objs = Counter(fmt.ctrl_id(d).strip() for t, _, d in recs if t == fmt.T['CTRL_HEADER'])
        tables = len({p.cell['table'] for p in paras if p.cell})
        out(f'SECTION {s} paragraphs body {kinds["body"]} cell {kinds["cell"]} other {kinds["other"]} tables {tables} '
            f'controls ' + ' '.join(f'{k}:{v}' for k, v in sorted(objs.items())))
    return pk


def main(args):
    info(args[0])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
