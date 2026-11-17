"""hwpx-docs command line.

  python lib/hd.py <command> [arguments]

Commands (each runs one module of the package hwpx_docs; `python lib/hd.py <command> --help` is not needed:
the arguments are in the module header and in the skills):
  build <spec.json> <out.hwpx>            core.build      spec -> HWPX
  read <in.hwpx> <out.json>                core.read       HWPX -> spec
  md <in.md> <out.hwpx> [...]              text.markdown   Markdown -> HWPX (presets)
  html <in.html> <out.hwpx> [--spec f]     text.html_css   any HTML (CSS computed like a browser) -> HWPX
  preset-from <sample> <out.json>          text.preset_from draft preset from an HWPX or a spec
  readability <in.hwpx|spec.json> [--fix f] check.readability
  check <in.hwpx> <checklist.md>           check.check_xml fidelity checklist
  measure <image.png> [--page-mm 210]      check.measure   lines, grid and text bands of a form image
  diff dump|diff|sdiff ...                 check.hwpx_diff XML difference of two HWPX files
  roundtrip <out_dir> <a.hwpx> ...         check.roundtrip HWPX -> spec -> HWPX -> render (Windows + Hangul)
  render hwpx|html|topng|side ...          render.render   page images (Windows + Hangul / Edge)
  img topng|side|overlay|compare ...       render.img      PNG/BMP convert, side by side, overlay, ink difference
  textwidth "<text>" [--font F] [--size S] core.textfit   width in pt in the real font (Windows)
  selftest                                 every module self-test (no Hangul needed)
Commands of feature packages (they register themselves, core/registry.py):"""
import os
import runpy
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

COMMANDS = {'build': 'core.build', 'read': 'core.read', 'md': 'text.markdown', 'html': 'text.html_css',
            'preset-from': 'text.preset_from', 'readability': 'check.readability', 'check': 'check.check_xml',
            'measure': 'check.measure', 'diff': 'check.hwpx_diff', 'roundtrip': 'check.roundtrip',
            'render': 'render.render', 'img': 'render.img', 'textwidth': 'core.textfit'}
# ponytail: the table above is the older modules' list; move an entry into its package's COMMANDS when that
# module changes next. New features never add a line here.


def main(argv):
    for stream in (sys.stdout, sys.stderr):    # pipes on Korean Windows default to cp949: ✓, ☑ and others fail
        stream.reconfigure(encoding='utf-8')
    from hwpx_docs.core import registry
    found = registry.commands()
    usage = __doc__ + ''.join(f'\n  {c} {u.split("  ")[0]:<36} {m:<15} {u.split("  ", 1)[-1]}'
                              for c, (m, _, u) in found.items())
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(usage)
        return 0
    if argv[0] == 'selftest':
        from hwpx_docs import selftest
        return selftest.main(argv[1:])
    both = set(found) & set(COMMANDS)
    if both:
        raise ValueError(f'commands in hd.py and in a package: {sorted(both)}')
    mod, pre, _ = found.get(argv[0]) or (COMMANDS.get(argv[0]), [], '')
    if not mod:
        print('unknown command:', argv[0])
        print(usage)
        return 2
    sys.argv = [f'hd {argv[0]}'] + pre + argv[1:]
    from hwpx_docs.core import protect
    try:
        runpy.run_module(f'hwpx_docs.{mod}', run_name='__main__', alter_sys=True)
    except protect.ProtectedDocument as e:       # protected file: say so, no traceback
        print(e)
        return protect.EXIT_CODE
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
