"""Self-test of every module (no Hangul needed): `python lib/hd.py selftest [--fixtures DIR] [--only core,text]`.

Prints "SELFTEST <module> PASS" per module and "SELFTEST ALL PASS" at the end; a failure prints the module and the
error and the exit code is 1. Fixtures: every *.hwpx in tests/fixtures is read -> built -> read again and the two
specs must be equal (238 samples saved by Hangul 2024: forms, 공문, and minimal-difference pairs per feature).
"""
from .core import tmpdir
import glob
import json
import os
import re
import sys
import traceback
import zipfile
from xml.dom import minidom

from .core import build, read

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def built(spec, name):
    """Build `spec`, check that every XML part parses, return {part: text}."""
    out = os.path.join(tmpdir.mkdtemp('hwpx_docs_t_'), name + '.hwpx')
    build.write(spec, out)
    parts = {}
    with zipfile.ZipFile(out) as z:
        for n in z.namelist():
            if n.endswith(('.xml', '.hpf', '.rdf')):
                parts[n] = z.read(n).decode('utf-8')
                minidom.parseString(parts[n])
    return out, parts


def t_core():
    build._selftest()
    from .core import protect
    protect._selftest()
    import importlib.util
    from .core import registry
    for cmd, (mod, _, _) in registry.commands().items():      # every registered command points at a module
        assert importlib.util.find_spec(f'{__package__}.{mod}'), (cmd, mod)
    spec = {'body': [{'p': '가나다', 'size': 12, 'bold': True, 'align': 'center', 'before': 6}]}
    path, _ = built(spec, 'core')
    back = read.read(path, os.path.join(os.path.dirname(path), 'core.json'))
    p = back['body'][0]
    assert p['p'] == '가나다' and p['size'] == 12 and p['bold'] and p['align'] == 'center' and p['before'] == 6, p
    # named styles: "class" takes a prop set; the item's own props win; several classes merge left to right
    spec = {'styles': {'big': {'size': 16, 'bold': True}, 'red': {'color': '#C00000'}},
            'body': [{'p': '제목', 'class': 'big red', 'bold': False},
                     {'table': {'cols': [40], 'rows': [[{'p': '셀', 'class': 'red'}]]}},
                     {'p': ['보통 ', {'t': '빨강', 'class': 'red'}]}]}
    path, _ = built(spec, 'class')
    back = read.read(path, os.path.join(os.path.dirname(path), 'class.json'))
    b = back['body']
    assert b[0]['size'] == 16 and not b[0].get('bold') and b[0]['color'] == '#C00000', b[0]
    assert b[1]['table']['rows'][0][0]['color'] == '#C00000', b[1]
    assert b[2]['p'][1]['color'] == '#C00000', b[2]


def t_text():
    from .text import mdparse, markdown, html_css
    from .core import textfit
    mdparse.selftest()
    markdown.selftest(tmpdir.mkdtemp('hwpx_docs_md_'))
    html_css.selftest()
    if os.name == 'nt':
        textfit.selftest()
    spec = {'body': [{'p': ['보통 ', {'t': '링크', 'link': 'https://example.com'}, {'footnote': '각주'}]}]}
    _, parts = built(spec, 'text')
    s = parts['Contents/section0.xml']
    assert 'HYPERLINK' in s and 'footNote' in s, 'link and footnote runs'


def t_objects():
    from .render import img
    d = tmpdir.mkdtemp('hwpx_docs_o_')
    img.save_png(os.path.join(d, 'a.png'), (40, 20, [bytes([0, 90, 200]) * 40] * 20))
    spec = {'body': [{'shapes': [{'type': 'rect', 'x': 20, 'y': 40, 'w': 60, 'h': 20, 'text': '글상자', 'fill': '#EAF1FB'},
                                 {'type': 'ellipse', 'x': 90, 'y': 40, 'w': 30, 'h': 20},
                                 {'type': 'line', 'x': 20, 'y': 70, 'x2': 120, 'y2': 70, 'arrow': 'end'}]},
                     {'pic': {'src': 'a.png', 'w': 20, 'h': 10}},
                     {'chart': {'type': 'bar', 'w': 120, 'h': 50, 'categories': ['가', '나'],
                                'series': [{'name': 's', 'values': [3, 5]}]}}]}
    out = os.path.join(d, 'objects.hwpx')
    build.write(spec, out, base=d)
    with zipfile.ZipFile(out) as z:
        s = z.read('Contents/section0.xml').decode('utf-8')
        names = z.namelist()
    minidom.parseString(s)
    assert '<hp:rect' in s and '<hp:ellipse' in s and '<hp:line' in s and '<hp:pic' in s, 'shapes and picture'
    assert any(n.startswith('BinData/') for n in names), 'embedded picture'
    assert s.count('<hp:rect') >= 3, 'chart bars are drawing objects'


def t_render():
    from .render import img, hwpcom
    img._selftest()
    hwpcom.selftest()


def t_check():
    from .check import readability, measure, check_xml, hwpx_diff
    readability.selftest()
    measure._selftest()
    path, _ = built({'body': [{'p': '성명', 'size': 11, 'bold': True}]}, 'check')
    ix = check_xml.Index(read.read(path, os.path.join(os.path.dirname(path), 'c.json')))
    assert check_xml.query(ix, 'text("성명").size') == 11 and check_xml.query(ix, 'text("성명").bold') is True
    assert not hwpx_diff.diff(path, path), 'a file has no difference from itself'


def t_fixtures(folder):
    files = sorted(glob.glob(os.path.join(folder, '*.hwpx')))
    assert files, f'no fixtures in {folder}'
    tmp = tmpdir.mkdtemp('hwpx_docs_f_')
    bad = []
    for f in files:
        n = os.path.splitext(os.path.basename(f))[0]
        a = read.read(f, os.path.join(tmp, n + '.a.json'))
        build.write(a, os.path.join(tmp, n + '.hwpx'), base=tmp)
        b = read.read(os.path.join(tmp, n + '.hwpx'), os.path.join(tmp, n + '.b.json'))
        if json.dumps(a, sort_keys=True) != json.dumps(b, sort_keys=True):
            bad.append(n)
    assert not bad, f'{len(bad)} of {len(files)} not stable: {bad[:8]}'
    print(f'  fixtures stable {len(files)}/{len(files)}')


def t_security():
    """Fixes of the security review (2026-11-15): a received file cannot write outside the output folder (`hd diff dump`), plant
    a file with a dangerous name or overwrite one next to the spec (`hd read`), put markup into the preview through a colour,
    or end a PowerShell string with a quote in a file name; `scan --fix` changes only text between tags."""
    from .check import hwpx_diff
    from .render import render
    from .textstyle import privacy
    d = tmpdir.mkdtemp('hwpx_docs_sec_')
    out = os.path.join(d, 'out')
    os.makedirs(out)
    for bad in ('../x.txt', '..\\x.txt', 'C:/x.txt', '/abs.txt', 'a/../../x.txt', 'Contents/'):
        assert hwpx_diff.safe_entry_path(out, bad) is None, bad
    assert hwpx_diff.safe_entry_path(out, 'Contents/section0.xml').startswith(os.path.realpath(out))
    # reader: names from the file are cleaned, kept inside the folder and never overwrite other content
    open(os.path.join(out, 'spec.json'), 'w').write('{}')
    r = read.Reader.__new__(read.Reader)
    r.out_dir, r.saved = out, set()
    assert r.save('BinData/version.dll', b'x') == 'version.dll.bin'
    assert r.save('..\\..\\evil.url', b'x') == 'evil.url.bin'
    assert r.save('spec.json', b'other') == 'spec.json.bin' and open(os.path.join(out, 'spec.json')).read() == '{}'
    open(os.path.join(out, 'mine.png'), 'wb').write(b'mine')
    assert r.save('mine.png', b'other') == 'mine_1.png' and open(os.path.join(out, 'mine.png'), 'rb').read() == b'mine'
    assert r.save('image1.png', b'p') == 'image1.png' and r.save('image1.png', b'p') == 'image1.png'
    # colours: a crafted value cannot leave the attribute
    root = read.safe_xml('<a xmlns:x="u" textColor="&quot;&gt;&lt;script&gt;" faceColor="#FF00FF" x:color="none"/>')
    assert root.get('textColor') == '#000000' and root.get('faceColor') == '#FF00FF'
    g = read.safe_xml('<g xmlns:hc="h"><hc:color value="&quot;/&gt;&lt;script&gt;"/><hc:color value="#112233"/></g>')
    assert [c.get('value') for c in g] == ['#000000', '#112233']           # gradient stops (security re-check)
    # PowerShell: quotes in a path are doubled inside a single-quoted literal
    assert render._q("a'b\u2019c") == "'a''b\u2019\u2019c'"
    # scan --fix: an account name that is also an attribute name or value stays there; in the text it goes
    old = os.environ.get('HWPX_DOCS_PRIVATE')
    os.environ['HWPX_DOCS_PRIVATE'] = 'zzuserzz'
    try:
        t = privacy._text_clean('<hh:x zzuserzz="1" lang="ZZUSERZZ"><hp:t>by zzuserzz</hp:t></hh:x>')
    finally:
        os.environ.pop('HWPX_DOCS_PRIVATE') if old is None else os.environ.update(HWPX_DOCS_PRIVATE=old)
    assert 'zzuserzz="1"' in t and 'lang="ZZUSERZZ"' in t and '<hp:t>by hwpx-docs</hp:t>' in t, t


def spec_keys_missing():
    """Spec keys of the builder column of docs/coverage.md (rows C1-C11) that docs/spec.md does not name: [(key, row id)].
    A key is a lower-case name in backticks (`dropcap`, `page.margin.gutter`, `{"xref": ...}`); commands (`hd ...`), paths and
    XML names (`styleIDRef`) are not keys."""
    spec = open(os.path.join(ROOT, 'docs', 'spec.md'), encoding='utf-8').read()
    keys = {}
    for line in open(os.path.join(ROOT, 'docs', 'coverage.md'), encoding='utf-8'):
        m = re.match(r'\| (C(\d+)\.\d+)', line)
        if not m or int(m.group(2)) > 11:
            continue
        builder = line.split('|')[6]
        for span in re.findall(r'`([^`]+)`', builder):
            words = span.split()
            if not words or span.startswith(('hd ', '-')) or '/' in span or span.endswith('.py'):
                continue
            names = re.findall(r'"([A-Za-z_]\w*)"\s*:', span) or [words[0]]
            for name in names:
                for part in name.split('.'):
                    if re.fullmatch(r'[a-z][a-z0-9_]*', part):
                        keys.setdefault(part, m.group(1))
    return sorted((k, row) for k, row in keys.items() if not re.search(r'(?<![\w])' + re.escape(k) + r'(?![\w])', spec))


def t_docs():
    """Every spec key that docs/coverage.md names (C1-C11) is in docs/spec.md: a first-time user finds each feature there."""
    missing = spec_keys_missing()
    assert not missing, f'spec keys of docs/coverage.md not in docs/spec.md: {missing}'


def t_tmpdir():
    """core/tmpdir.py removes its folders, and a self-test run leaves no new folder in %TEMP% (a run that left 12 MB filled the disk of C:)."""
    import shutil
    import subprocess
    import tempfile
    from .core import tmpdir
    d = tmpdir.mkdtemp('hwpx_docs_tmpchk_')
    open(os.path.join(d, 'a.txt'), 'w').write('x')
    tmpdir.cleanup()
    assert not os.path.exists(d), 'cleanup() removes the folder with its files'
    probe = tempfile.mkdtemp(prefix='hwpx_docs_tmpprobe_')          # the run below gets this as its %TEMP%; removed here
    try:
        quick = 'core,text,objects,check,chart,convert,edit,extract,fields,gongmun,page,secure,table,textstyle'
        env = dict(os.environ, TEMP=probe, TMP=probe, TMPDIR=probe)
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'lib', 'hd.py'), 'selftest', '--only', quick], env=env,
                           capture_output=True, text=True, encoding='utf-8')
        assert r.returncode == 0, r.stdout[-800:] + r.stderr[-800:]
        left = [n for n in os.listdir(probe) if n != 'gen_py']      # gen_py: the pywin32 cache, one small fixed folder
        assert not left, f'self-tests left in %TEMP%: {left[:8]}'
    finally:
        shutil.rmtree(probe, ignore_errors=True)


TESTS = {'core': t_core, 'text': t_text, 'objects': t_objects,
         'render': t_render, 'check': t_check, 'tmpdir': t_tmpdir, 'docs': t_docs, 'security': t_security}
# ponytail: TESTS above are the older modules' tests; move one into its package's selftest() when that module
# changes next. A feature package registers its own selftest() (core/registry.py); nothing is added here.
# (page and gongmun already did: page/__init__.py, gongmun/__init__.py.)


def main(args):
    from .core import registry
    for name, fn in registry.tests().items():
        if name in TESTS:
            raise ValueError(f'self-test "{name}" in selftest.py and in its package')
        TESTS[name] = fn
    only = args[args.index('--only') + 1].split(',') if '--only' in args else list(TESTS) + ['fixtures']
    fixtures = args[args.index('--fixtures') + 1] if '--fixtures' in args else os.path.join(ROOT, 'tests', 'fixtures')
    failed = []
    for name in only:
        try:
            TESTS[name]() if name in TESTS else t_fixtures(fixtures)
            print(f'SELFTEST {name} PASS')
        except Exception:
            failed.append(name)
            print(f'SELFTEST {name} FAIL')
            traceback.print_exc(limit=3)
    print('SELFTEST ALL PASS' if not failed else f'SELFTEST FAILED: {", ".join(failed)}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
