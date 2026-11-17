"""Where else does a word stand in a .hwp (rule HW111).

`hd hwp edit --replace` and `hd guard --forbid` look at the body text. An old word can also stand in the revision history
(`DocHistory`), the summary information (title, subject, author, comments), the field and hyperlink strings of the body records
(a field command, a hyperlink address, a bookmark name), DocInfo and the preview. This module searches EVERY stream (inflated where
Hangul deflates it) for a word in UTF-16LE, UTF-8 and cp949, leaving out only the paragraph texts of the body (the callers have
those) and the script streams.

  hits(pk, words) -> {word: [stream or 'BodyText/Section0 (record name)', ...]}
  history(pk)     -> names of the revision history streams (`DocHistory`...), which keep old versions of the text"""
from . import fmt


_NAME = {v: k for k, v in fmt.T.items()}


def _encodings(word):
    out = {word.encode('utf-16-le', 'surrogatepass'), word.encode('utf-8')}
    try:
        out.add(word.encode('cp949'))
    except UnicodeEncodeError:
        pass
    return [e for e in out if len(e) >= 2]


def _streams(pk):
    """(name, bytes) of every stream; a deflated one is inflated, a record stream as a list of (tag, data) in `recs`."""
    for name, s in pk.streams.items():
        if 'SCRIPTS' in [p.upper() for p in name.split('/')[:-1]]:
            continue
        data = s.data
        if name == 'DocInfo' or name.startswith(('BodyText/', 'ViewText/')):
            continue                                    # record streams: below, record by record
        if name.upper().startswith('DOCHISTORY') and pk.compressed:
            try:
                data = fmt.inflate(data)
            except Exception:
                pass
        yield name, data


def hits(pk, words):
    """{word: [where, ...]}: every place a word stands except the paragraph texts of BodyText (PARA_TEXT)."""
    found = {}
    words = [w for w in words if w]
    enc = {w: _encodings(w) for w in words}
    for name, data in _streams(pk):
        for w in words:
            if any(e in data for e in enc[w]):
                found.setdefault(w, []).append(name)
    for name in ['DocInfo'] + list(pk.sections):
        try:
            recs = pk.records(name)
        except Exception:
            continue
        for tag, lvl, d in recs:
            if tag == fmt.T['PARA_TEXT']:
                continue
            for w in words:
                if any(e in d for e in enc[w]):
                    where = f'{name} (record {_NAME.get(tag, hex(tag))})'
                    if where not in found.setdefault(w, []):
                        found[w].append(where)
    return found


def history(pk):
    return [n for n in pk.streams if n.upper().startswith('DOCHISTORY')]


def selftest():
    class S:
        def __init__(self, data):
            self.data = data

    class P:
        compressed = False
        sections = ['BodyText/Section0']
        streams = {'DocHistory/VersionLog0': S('old secret'.encode('utf-16-le')), '\x05HwpSummaryInformation': S('Title: 비밀문서'.encode('utf-16-le')),
                   'Scripts/DefaultJScript': S('secret'.encode('utf-16-le'))}

        def records(self, name):
            return [(fmt.T['PARA_TEXT'], 1, 'secret'.encode('utf-16-le')), (fmt.T['CTRL_HEADER'], 1, b'klh%' + 'secret'.encode('utf-16-le'))] \
                if name == 'BodyText/Section0' else []
    pk = P()
    got = hits(pk, ['secret', '비밀문서', 'absent'])
    assert got['secret'] == ['DocHistory/VersionLog0', 'BodyText/Section0 (record CTRL_HEADER)'], got
    assert got['비밀문서'] == ['\x05HwpSummaryInformation'] and 'absent' not in got, got
    assert history(pk) == ['DocHistory/VersionLog0']
    print('RESIDUE SELFTEST PASS')


def integration(d):
    """A file whose DocHistory and summary information keep the old sentence: `edit --replace` and `guard --forbid` say so."""
    import contextlib
    import io
    import os
    from . import cfb, edit, guard, tests
    base = os.path.join(d, 'res_base.hwp')
    tests.build(base)
    root = cfb.read(open(base, 'rb').read())
    old = '아래 표에 적어 주십시오.'
    root.add(cfb.Entry('DocHistory', cfb.STORAGE)).add(cfb.Entry('VersionLog0', cfb.STREAM, ('log: ' + old).encode('utf-16-le')))
    root.add(cfb.Entry('\x05HwpSummaryInformation', cfb.STREAM, ('subject ' + old).encode('utf-16-le')))
    src, dst = os.path.join(d, 'res_src.hwp'), os.path.join(d, 'res_out.hwp')
    with open(src, 'wb') as f:
        f.write(cfb.build(root))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert edit.main(['edit', src, dst, '--replace', old + '=아래에 써 주십시오.']) == 0
    text = buf.getvalue()
    assert 'RESIDUE' in text and 'DocHistory/VersionLog0' in text and 'HwpSummaryInformation' in text, text
    assert 'NOTE the revision history' in text, text
    lines = []
    guard.report(src, dst, forbid=[old], out=lines.append)
    assert any('also in' in x and 'DocHistory' in x for x in lines) and any('GUARD NOTE the revision history' in x for x in lines), lines
    print('RESIDUE INTEGRATION PASS')
