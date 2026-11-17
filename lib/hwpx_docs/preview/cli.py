"""`hd preview <in.hwpx> [out_dir] [--dpi 96] [--no-png]` and the `preview` backend of `hd render hwpx`."""
import os
import sys

from .output import render_files


def render_backend(path, out_dir, dpi=96):
    """Backend of `hd render hwpx`: prints "PREVIEW OK <file> pages <n>" and returns the PNG paths."""
    pngs = render_files(path, out_dir, dpi)
    print('PREVIEW OK', path, 'pages', len(pngs))
    return pngs


def pages_backend(path):
    """Backend `pages` (fields package, 차례 and 색인 page numbers): the SVG text of every page of an HWPX."""
    from .flow import render_pages
    return [svg for _, _, svg in render_pages(path)]


def main(args):
    dpi = 96
    if '--dpi' in args:
        i = args.index('--dpi')
        dpi = int(args[i + 1])
        del args[i:i + 2]
    png = '--no-png' not in args
    args = [a for a in args if a != '--no-png']
    if not args:
        print(__doc__)
        return 2
    out = args[1] if len(args) > 1 else os.path.dirname(os.path.abspath(args[0]))
    for p in render_files(args[0], out, dpi, png):
        print('PAGE', p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
