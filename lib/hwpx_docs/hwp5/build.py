"""`hd hwp fromhwpx` and `hd hwp build`: make an .hwp (HWP 5.0) without Hangul.

  hd hwp fromhwpx <in.hwpx> <out.hwp>       HWPX -> .hwp (fromowpml: OWPML -> records -> compound file)
  hd hwp build <spec.json> <out.hwp>        spec -> HWPX with core.build (the builder Hangul checked) -> .hwp; there is no
                                            second builder: every document the spec builder can make is made the same way

An element with no record yet stops the run: `UNSUPPORTED <element> <where>` on stdout, exit 5 (nothing is dropped silently,
no half-written .hwp stays). Rules HW37-HW44.
"""
import json
import os
import sys

from ..core import tmpdir
from . import fromowpml


def build(spec_path, out_path):
    """spec.json -> out.hwp (through a temporary HWPX)."""
    from ..core import build as core_build
    spec = json.load(open(spec_path, encoding='utf-8'))
    tmp = os.path.join(tmpdir.mkdtemp('hwp5_build_'), 'spec.hwpx')
    core_build.write(spec, tmp, os.path.dirname(os.path.abspath(spec_path)))
    return fromowpml.convert(tmp, out_path)


def main(args):
    """args = ['fromhwpx' | 'build', input, output]."""
    if len(args) != 3 or args[0] not in ('fromhwpx', 'build'):
        print('usage: hd hwp fromhwpx <in.hwpx> <out.hwp> | hd hwp build <spec.json> <out.hwp>')
        return 2
    try:
        (fromowpml.convert if args[0] == 'fromhwpx' else build)(args[1], args[2])
    except fromowpml.Unsupported as e:
        print(f'UNSUPPORTED {e}')
        return 5
    print(f'HWP WRITTEN {args[2]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
