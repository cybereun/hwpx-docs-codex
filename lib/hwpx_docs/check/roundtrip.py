"""Round trip: Hangul HWPX -> spec (hwpx2spec) -> HWPX (hwpx_build) -> pages -> compare with the original.

  python roundtrip.py <out_dir> <a.hwpx> [<b.hwpx> ...]

For each file writes <out_dir>/<stem>/: spec.json, rebuilt.hwpx, page PNGs of both, side_p<N>.png
(original left, rebuilt right) and prints one line:
  RT <stem> pages <orig>/<rebuilt> ink_diff <max % over pages> open <OK|FAIL>
ink_diff 0 = same ink layout (scripts/img.py compare). One Hangul instance renders all files.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from ..core import read as hwpx2spec
from ..core import build as hwpx_build
from ..render import img
from ..render import render
from ..render.hwpcom import Hwp


def main(out_dir, paths):
    jobs = []
    for p in paths:
        stem = os.path.splitext(os.path.basename(p))[0]
        d = os.path.join(out_dir, stem)
        os.makedirs(d, exist_ok=True)
        shutil.copyfile(p, os.path.join(d, 'original.hwpx'))
        spec_path = os.path.join(d, 'spec.json')
        spec = hwpx2spec.read(p, spec_path)
        json.dump(spec, open(spec_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        hwpx_build.write(spec, os.path.join(d, 'rebuilt.hwpx'), d)
        jobs.append((stem, d))
    files = [os.path.join(d, f) for _, d in jobs for f in ('original.hwpx', 'rebuilt.hwpx')]
    res = render.hwpx_pages(files, out_dir, stems={f: os.path.join(os.path.basename(os.path.dirname(f)),
                                                                   f[:-5].split(os.sep)[-1]) for f in files})
    for stem, d in jobs:
        a, b = res.get(os.path.join(d, 'original.hwpx')), res.get(os.path.join(d, 'rebuilt.hwpx'))
        if not a or not b:
            print('RT', stem, 'open FAIL', 'original' if not a else 'rebuilt')
            continue
        diffs = []
        for n, (pa, pb) in enumerate(zip(a, b), start=1):
            ia, ib = img.load(pa), img.load(pb)
            diffs.append(img.compare(ia, ib))
            img.save_png(os.path.join(d, f'side_p{n}.png'), img.side_by_side([ia, ib]))
            img.save_png(os.path.join(d, f'overlay_p{n}.png'), img.overlay(ia, ib))
        print('RT', stem, 'pages', f'{len(a)}/{len(b)}', 'ink_diff', '%.2f' % max(diffs or [100]), 'open OK')
    for k, v in hwpx2spec.unsupported.items():
        print('UNSUPPORTED', k, v)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
