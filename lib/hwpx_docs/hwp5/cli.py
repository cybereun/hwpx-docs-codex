"""`hd hwp <sub> ...`: the .hwp (HWP 5.0) commands.

  hd hwp info <in.hwp>                                   version, flags, streams, sections, paragraphs, tables
  hd hwp text <in.hwp>                                   the text, one paragraph per line
  hd hwp slots <in.hwp> [--json f]                       editable slots (as `hd slots`)
  hd hwp edit <in.hwp> <out.hwp> [...]                   change text only (as `hd edit`)
  hd hwp guard <original.hwp> <edited.hwp> [...]         same form? structure, layout budget, residue (+ --render dir)
  hd hwp render <in.hwp> [out_dir] [--backend auto|preview|hangul] [--dpi 96]   page images
  hd hwp compare <before.hwp> <after.hwp> <out_dir> [--backend ...]             pages before / after, differences
  hd hwp tospec <in.hwp> <out.json>                      HWP -> spec (the builder's input; no Hangul)
  hd hwp tohwpx <in.hwp> <out.hwpx>                      HWP -> HWPX record by record (no Hangul; UNSUPPORTED <what> <where> and exit 5 for a record it cannot map)
  hd hwp fromhwpx <in.hwpx> <out.hwp>                    HWPX -> .hwp (no Hangul; UNSUPPORTED <what> <where> and exit 5 for an element it cannot write)
  hd hwp build <spec.json> <out.hwp>                     spec -> HWPX (core.build) -> .hwp (no Hangul; exit 5 = UNSUPPORTED as above, 3 = Hwp5Error)
  hd hwp selftest [DIR or file ...]                      self-test; with paths: the no-Hangul checks on every .hwp
"""
import sys

SUBS = {'text': 'edit', 'slots': 'edit', 'edit': 'edit', 'guard': 'guard', 'info': 'info',
        'render': 'render', 'compare': 'render', 'tospec': 'tospec', 'tohwpx': 'owpml', 'selftest': 'tests',
        'fromhwpx': 'build', 'build': 'build'}


def main(args):
    if not args or args[0] not in SUBS:
        print(__doc__)
        from . import NOTICE
        print(NOTICE)
        return 2
    import importlib
    mod = importlib.import_module(f'{__package__}.{SUBS[args[0]]}')
    from .fmt import Hwp5Error
    try:
        return mod.main(args if SUBS[args[0]] in ('edit', 'render', 'tospec', 'build') else args[1:]) or 0
    except Hwp5Error as e:
        print(e)
        return 3


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
