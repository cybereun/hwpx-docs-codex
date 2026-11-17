"""Command line of the privacy add-on: python pv.py <command> ...   (list, forget, purge, audit, add, calc, scan, mask-copy, consent, enable, disable,
status, selftest; `python pv.py help`). Not an `hd` command: the core has two hook points for add-ons and no more.

The core library (`lib/` of hwpx-docs) is found through the environment variable HWPX_DOCS_LIB, the repository layout (`addons/<this>/../../lib`)
or the plugin cache (`~/.claude/plugins/cache/*/hwpx-docs/*/lib`); without it a document is still read as a package, but not by its form slots.
"""
import glob
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _core():
    cands = [os.environ.get('HWPX_DOCS_LIB', ''), os.path.join(HERE, '..', '..', '..', 'lib')]
    cands += sorted(glob.glob(os.path.join(os.path.expanduser('~'), '.claude', 'plugins', 'cache', '*', 'hwpx-docs', '*', 'lib')), reverse=True)
    for c in cands:
        if c and os.path.isdir(os.path.join(c, 'hwpx_docs')):
            sys.path.insert(0, os.path.abspath(c))
            return


_core()
from hwpxpriv import cli  # noqa: E402

if __name__ == '__main__':
    sys.exit(cli.main(sys.argv[1:]))
