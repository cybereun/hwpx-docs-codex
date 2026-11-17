"""Fill synthetic people into forms on the local machine (nothing leaves it): the government forms (.hwp) of a folder and the HWPX examples.

  python tools/privacy/fill.py <out dir> --gov <folder of blank .hwp forms> [--limit N]

Per document one fake person (gen.py). Each labelled value cell whose label names a field gets that field; the narrative
(a name after a compound label `신청인 성명 ...`, a sensitive sentence, a phone, a second name in prose) goes to an empty body paragraph or cell; the name is also written to a second empty cell that has no label
(a typed value the labels cannot find). `<out>/canaries.json` = {document: {"canaries": [[kind, value]...], "sens": sentence}}.
The filled files are never put in the repository.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'lib'))
import gen  # noqa: E402

LABELS = [
    (r'주민\s*등록\s*번호|주민\s*번호', 'rrn'), (r'생\s*년\s*월\s*일', 'birth'), (r'성\s*명|이\s*름|대표자|신청인', 'name'),
    (r'전화|연락처|휴대', 'phone'), (r'주\s*소|소재지|거주지', 'address'), (r'이메일|전자우편', 'email'), (r'계좌', 'bank_no'),
    (r'카드', 'card'), (r'차량', 'plate'), (r'여권', 'passport'), (r'면허', 'driving'), (r'사업자', 'brn'), (r'우편\s*번호', 'postcode'),
    (r'직장|근무처|소속', 'employer'), (r'학교', 'school'),
]
CIRCLED = re.compile(r'^[\s①-⑳㉑-㉟\d.()]+')


def field_of(label):
    t = CIRCLED.sub('', label or '')
    for rx, f in LABELS:
        if re.search(rx, t):
            return f
    return None


def fill_one(src, dst, seed, blank_text):
    if src.lower().endswith('.hwp'):
        from hwpx_docs.hwp5.edit import Doc
    else:
        from hwpx_docs.edit.edit import Doc
    rows = Doc(src).slots()
    for attempt in range(20):                              # a fake value must not already be a word of the blank form
        p = gen.person(seed + attempt * 100000)
        if not any(v in blank_text for _, v in gen.canaries(p)):
            break
    values, used = {}, []
    for r in rows:
        f = field_of(r['label'])
        if f and f in p and not r['text'].strip(' ○_'):
            values[r['key']] = p[f]
            if f in ('name', 'rrn', 'phone', 'email', 'bank_no', 'card', 'plate', 'passport', 'driving', 'brn', 'employer', 'school'):
                used.append(('bank' if f == 'bank_no' else f, p[f]))
            elif f == 'address':
                used.append(('address', p['address'].split(',')[0]))
    empty = [r for r in rows if not r['text'].strip() and r['kind'] in ('body', 'cell') and not r['label'] and r['key'] not in values]
    # a compound label before a name, and a second name in prose with a title: the two layouts together once hid the first name
    narrative = (f'신청인 성명 {p["name"]} {p["sens"]} 연락처 {p["tel"]}, 차량 {p["plate"]}. '
                 f'담당자 {p["family"]} 주무관에게 문의하십시오.')
    free = []
    if empty:
        values[empty[0]['key']] = narrative
        used += [('name', p['name']), ('name', p['family']), ('tel', p['tel']), ('plate', p['plate'])]
        if len(empty) > 1:
            values[empty[1]['key']] = p['name']
            free.append(empty[1]['key'])
    if not values:
        return None
    vp = dst + '.values.json'
    json.dump(values, open(vp, 'w', encoding='utf-8'), ensure_ascii=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith('HWPX_DOCS_ADDONS')}
    r = subprocess.run([sys.executable, '-X', 'utf8', os.path.join(ROOT, 'lib', 'hd.py'), 'edit', src, dst, '--values', vp, '--allow-missing'],
                       capture_output=True, env=env)
    os.remove(vp)
    if not os.path.exists(dst):
        return None
    uniq = sorted(set(used))
    return {'canaries': uniq, 'sens': p['sens'], 'free': free, 'person': p['seed']}


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    out = argv[0]
    if '--gov' not in argv:
        print('usage: fill.py <out dir> --gov <folder of blank .hwp forms> [--limit N]')
        return 2
    gov = argv[argv.index('--gov') + 1]
    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else 10 ** 9
    os.makedirs(os.path.join(out, 'gov'), exist_ok=True)
    os.makedirs(os.path.join(out, 'hwpx'), exist_ok=True)
    srcs = [(os.path.join(gov, f), os.path.join(out, 'gov', f)) for f in sorted(os.listdir(gov)) if f.lower().endswith('.hwp')][:limit]
    ex = os.path.join(ROOT, 'examples')
    for d in sorted(os.listdir(ex)):
        p = os.path.join(ex, d, 'form.hwpx')
        if os.path.exists(p):
            srcs.append((p, os.path.join(out, 'hwpx', d + '.hwpx')))
    for f in ('bogoseo.hwpx', 'box_doc.hwpx'):
        p = os.path.join(ROOT, 'tests', 'fixtures', f)
        if os.path.exists(p):
            srcs.append((p, os.path.join(out, 'hwpx', f)))
    res, skipped = {}, 0
    for i, (src, dst) in enumerate(srcs):
        try:
            if src.lower().endswith('.hwp'):
                from hwpx_docs.hwp5.edit import Doc
            else:
                from hwpx_docs.edit.edit import Doc
            blank = '\n'.join(r['text'] for r in Doc(src).slots())
            info = fill_one(src, dst, 1000 + i, blank)
        except Exception as e:
            print('SKIP', os.path.basename(src), type(e).__name__, str(e)[:80])
            info = None
        if info:
            info['source'] = src
            res[os.path.relpath(dst, out).replace('\\', '/')] = info
        else:
            skipped += 1
    json.dump(res, open(os.path.join(out, 'canaries.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n = sum(len(v['canaries']) for v in res.values())
    print(f'FILL {len(res)} documents filled, {skipped} without fillable cells, {n} canary values -> {out}')


if __name__ == '__main__':
    main(sys.argv[1:])
