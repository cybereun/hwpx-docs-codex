"""Check a 공문 spec against the official 기안문 form (fields and wording, docs/gongmun-defaults.md).

  python lib/hd.py gongmun-check <spec.json>     prints "GMnn <message>" per finding and "GONGMUN OK" when there is none

Data in, findings out. Only fields and wording are checked (the label words, 2타 after 수신/제목/붙임, 끝 forms,
전화번호/팩스번호, the form of the 시행 line). Margins, fonts and sizes are not official for a 기안문 (convention).
"""
from ..core import tmpdir
import json
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))


def texts(spec):
    """Paragraph texts of the top-level blocks of a spec (tables and objects are skipped)."""
    out = []
    for b in spec.get('body', []):
        p = b.get('p') if isinstance(b, dict) else b
        if isinstance(p, list):
            p = ''.join(r if isinstance(r, str) else r.get('t', '') for r in p)
        if isinstance(p, str):
            out.append(p)
    return out


RULES = [      # (id, test of one line -> message or None)
    ('GM01', lambda s: '기안자/검토자/결재권자 are not written in the signer line (별지 제1호서식 비고)'
     if re.search(r'(^|\s{2,})(기안자|검토자|결재권자)\s+\S', s) else None),
    ('GM02', lambda s: 'contact line: 전화번호(지역번호) and 팩스번호, not 전화 or 전송 (작성방법 10)'
     if s.startswith('전화') and (not s.startswith('전화번호') or '전송' in s or '팩스번호' not in s) else None),
    ('GM03', lambda s: '시행 번호(시행일): no space before the parenthesis (작성방법 7)'
     if re.match(r'시행 \S+ \(', s) else None),
    ('GM04', lambda s: '수신 and 제목: 2타 (two spaces) after the label (편람 §4 다 2)'
     if re.match(r'(수신|제목) \S', s) else None),
    ('GM05', lambda s: '끝: 2타 (two spaces) after the last character (시행규칙 제4조⑤)'
     if re.search(r'\S 끝\.$', s) else None),
]


def check(spec):
    """[(id, message, text of the line)] of a 공문 spec; [] when the form is right."""
    found = []
    for line in texts(spec):
        for rid, test in RULES:
            msg = test(line)
            if msg:
                found.append((rid, msg, line))
    return found


def main(args):
    spec = json.load(open(args[0], encoding='utf-8'))
    found = check(spec)
    for rid, msg, line in found:
        print(f'{rid} {msg}: {line[:40]}')
    print('GONGMUN OK' if not found else f'GONGMUN {len(found)} finding(s)')
    return 1 if found else 0


def selftest():
    import zipfile
    from xml.dom import minidom
    from ..core import build

    def load(rel):
        return json.load(open(os.path.join(ROOT, rel), encoding='utf-8'))

    for rel in ('templates/gongmun.json', 'examples/gongmun-notice/notice.json'):
        d = load(rel)
        assert d['page']['size'] == 'A4', rel                                  # the only official page value
        assert not check(d), (rel, check(d))
        body = [b for b in d['body'] if isinstance(b.get('p'), str)]
        text = '\n'.join(b['p'] for b in body)
        assert '협조자 ' in text and '전송' not in text, rel
        assert re.search('관련: .+\\(.+“.+”\\)호', text), f'{rel}: 관련 문서 = 기관 번호(날짜, “제목”)호 (편람 §5 다 2)'
        classes = [b.get('class') for b in body]
        assert classes.index('sender') < min(i for i, b in enumerate(body) if b['p'].startswith('수신자  ')) \
            < classes.index('tail_first'), f'{rel}: 수신자 line between 발신명의 and the signer line'
        out = os.path.join(tmpdir.mkdtemp('hwpx_docs_gm_'), 'gm.hwpx')
        build.write(d, out)
        with zipfile.ZipFile(out) as z:
            minidom.parseString(z.read('Contents/section0.xml'))
    bad = {'body': [{'p': '수신 ○○○'}, {'p': '제목 ○○'}, {'p': '기안자 ○○ ○○○    검토자 ○○ ○○○'},
                    {'p': '시행 ○○과-1 (2026. 1. 1.)'}, {'p': '전화 02-000-0000  전송 02-000-0001'},
                    {'p': '2. ○○ 1부. 끝.'}, {'p': '기안자는 검토한다.'}]}
    assert [r for r, _, _ in check(bad)] == ['GM04', 'GM04', 'GM01', 'GM03', 'GM02', 'GM05'], check(bad)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
