"""`python scripts/pv.py <command>`: the commands of the privacy add-on. Nothing here prints a value of the vault.

  list [--json]                       tags (id, kind, documents, attributes); never values
  forget <document>                   remove the values that came only from that document
  purge --yes                         delete the whole vault (values, key files)
  audit [--json]                      what was masked, resolved, revealed, blocked (counts, hashes; for an inspection)
  add --stdin [--kind private]        add a word of your own (K) read from the standard input, so it never enters a prompt
  calc "<expression>"                 safe computation on tagged values (age, birthdate, gender, partial, count ...)
  scan <file>                         counts of personal data per kind in a text file or an HWPX (no values)
  mask-copy <in> <out> [--images placeholder|strip|keep]
                                      a copy for the model: HWPX with every value and hidden place covered; text with tags
  consent <tag|type:kind> [--fine]    show one tag (or one kind) to the model: only from a terminal, logged
  enable [--no-enforce] | disable     the fixed settings file that loads the layer for every hd call (disable: terminal only)
  status                              mode, vault backend, packs
"""
import contextlib
import io
import json
import os
import sys
import time
from collections import Counter

from . import calc, detect, docscan, engine, settings, vault as V


def _out(sess, text):
    print(sess.mask(text))


def main(argv):
    sys.stdout.reconfigure(encoding='utf-8')
    if not argv or argv[0] in ('-h', '--help', 'help'):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    fn = globals().get('cmd_' + cmd.replace('-', '_'))
    if not fn:
        print(f'unknown vault command: {cmd}\n{__doc__}')
        return 2
    with V.lock():
        return _run(fn, cmd, args)


def _run(fn, cmd, args):
    sess = engine.Session(['vault', cmd] + args)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):               # whatever a command prints (a file name with a name in it) is masked too
            rc = fn(sess, args)
    except (engine.PrivacyError, calc.CalcError) as e:
        buf.write(f'VAULT {cmd.upper()} FAIL: {e}\n')
        rc = 1
    text = sess.mask(buf.getvalue())
    sess.vault.save()
    sys.stdout.write(text)
    return rc or 0


def cmd_list(sess, args):
    rows = []
    for tid, e in sess.vault.data['entries'].items():
        rows.append({'tag': tid, 'kind': e['kind'], 'group': (sess.det.kinds.get(e['kind']).group if e['kind'] in sess.det.kinds else '-'),
                     'documents': e['sources'], 'attrs': [t for _, t in e.get('attrs', [])]})
    if '--json' in args:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f'{r["tag"]:<14} {r["kind"]:<10} {r["group"]} {"·".join(r["attrs"]):<24} {", ".join(r["documents"])}')
        print(f'VAULT LIST {len(rows)} tags ' + str(dict(Counter(r["kind"] for r in rows))))
    return 0


def cmd_forget(sess, args):
    if not args:
        print('usage: vault forget <document file name>')
        return 2
    n = sess.vault.forget(V.src_id(args[0]))
    V.audit('forget', doc=V.src_id(args[0]), removed=n)
    print(f'VAULT FORGET {n} tags removed')
    return 0


def cmd_purge(sess, args):
    if '--yes' not in args:
        print('this deletes every stored value; the documents themselves stay. Run `vault purge --yes`.')
        return 2
    n = V.purge()
    V.audit('purge', files=n)
    sess.vault.dirty = False
    print(f'VAULT PURGE {n} files deleted')
    return 0


def cmd_audit(sess, args):
    recs = V.audit_records()
    if '--json' in args:
        print(json.dumps(recs, ensure_ascii=False, indent=1))
        return 0
    c = Counter()
    masked, denied, blocked, reveals, residual = Counter(), 0, 0, 0, 0
    for r in recs:
        c[r['event']] += 1
        for k, n in (r.get('masked') or {}).items():
            masked[k] += n
        reveals += r['event'] in ('reveal', 'consent')
        denied += r['event'] == 'deny'
        blocked += r['event'] == 'prompt-block'
        residual += r.get('residual', 0) or 0
    print(f'AUDIT {len(recs)} records, events {dict(c)}')
    print(f'AUDIT masked by kind {dict(masked)}')
    print(f'AUDIT hook denials {denied}, prompt blocks {blocked}, consents/reveals {reveals}, residual findings {residual}')
    for r in recs[-10:]:
        print('AUDIT last:', json.dumps({k: v for k, v in r.items() if k != 't'}, ensure_ascii=False))
    return 0


def cmd_add(sess, args):
    if '--stdin' not in args:
        print('usage: vault add --stdin [--kind private]   (type or pipe the word; it is not shown)')
        return 2
    word = sys.stdin.readline().rstrip('\r\n')
    if len(word) < 2:
        print('too short')
        return 1
    sess.vault.data.setdefault('terms', [])
    if word not in sess.vault.data['terms']:
        sess.vault.data['terms'].append(word)
        sess.vault.dirty = True
    V.audit('add-term', n=len(sess.vault.data['terms']))
    print(f'VAULT ADD ok, {len(sess.vault.data["terms"])} words of your own')
    return 0


def cmd_calc(sess, args):
    if not args:
        print('usage: vault calc "<expression>"')
        return 2

    def resolve(tag):
        tid = tag.strip('⟪⟫').split('｜')[0]
        e = sess.vault.get(tid)
        if e is None:
            raise engine.PrivacyError(f'unknown tag {tag}')
        raw = calc.Raw(e['value'])
        raw.kind = e['kind']
        return raw
    value, shown = calc.evaluate(' '.join(args), resolve)
    if shown:
        print(f'CALC {value}')
    else:
        tid = sess.vault.add('calc', '계산', str(value), False, 'calc', [], '')
        print(f'CALC {engine.OPEN}{tid}{engine.CLOSE}')
    V.audit('calc', shown=shown)
    return 0


def cmd_scan(sess, args):
    if not args or not os.path.isfile(args[0]):
        print('usage: vault scan <file>')
        return 2
    path = args[0]
    if path.lower().endswith('.hwpx'):
        text = '\n'.join(docscan.hwpx_texts(path))
        hidden = docscan.hidden_values(path)
    else:
        text = open(path, encoding='utf-8', errors='replace').read()
        hidden = []
    spans = sess._spans(text)
    c = Counter(s.kind for s in spans)
    print(f'SCAN {os.path.basename(path)}: {len(spans)} values {dict(c)}; hidden places {len(hidden)}; '
          f'dictionary terms {len(sess.det.sensitive(text))}')
    return 0


def cmd_mask_copy(sess, args):
    paths = [a for a in args if not a.startswith('-')]
    if len(paths) != 2:
        print('usage: vault mask-copy <in> <out> [--images placeholder|strip|keep]')
        return 2
    images = args[args.index('--images') + 1] if '--images' in args else 'placeholder'
    src, dst = paths
    kind = docscan.sniff(src)
    if kind == 'hwp':
        print('MASKCOPY refused: an HWP 5 file cannot be covered as it is. Save it as .hwpx in Hangul first (File > Save as), then run mask-copy on that.')
        return 2
    if kind == 'hwpx':
        from . import redact
        st = redact.redact(src, dst, sess, images=images)
        print(f'MASKCOPY OK {os.path.basename(dst)} ' + str(st))
    else:
        from .gates import decode_text
        with open(src, 'rb') as f:
            raw = f.read()
        text = decode_text(raw)
        if text is None:
            print('MASKCOPY refused: this is not a text file or a Hangul document (a picture or another binary cannot be covered; it is not read directly either).')
            return 2
        open(dst, 'w', encoding='utf-8').write(sess.mask(text, learn_source=V.src_id(src)))
        print(f'MASKCOPY OK {os.path.basename(dst)} text masked')
    V.audit('mask-copy', doc=V.src_id(src), mode=images)
    return 0


def cmd_consent(sess, args):
    if not args:
        print('usage: vault consent <tag|type:kind> [--fine]')
        return 2
    if not (sys.__stdin__.isatty() and sys.__stdout__.isatty()):
        print('VAULT CONSENT refused: a consent can only be given by you, from a terminal (not from a command that a model runs).')
        V.audit('consent-refused')
        return 1
    target, fine = args[0], '--fine' in args
    what, name = ('types', target[5:]) if target.startswith('type:') else ('tags', target.strip('⟪⟫'))
    print(f'The model will see the real {"value of " if what == "tags" else "values of kind "}{name}'
          f'{" (and finer attributes)" if fine else ""}; the cloud may keep it. Type the word yes to confirm: ', end='')
    if input().strip().lower() != 'yes':
        print('cancelled')
        return 1
    V.add_consent(what, name, fine, 'terminal')
    print('CONSENT logged')
    return 0


def cmd_selftest(sess, args):
    from . import normalize, validators
    validators.selftest()
    V.selftest()
    normalize.selftest()
    v, shown = calc.evaluate('count(1,2,3,4,5)', lambda t: t)
    assert shown and v == 5
    try:
        calc.evaluate('__import__("os")', lambda t: t)
        raise AssertionError('calc ran code')
    except calc.CalcError:
        pass
    from . import ioflow
    for word, p, want in (('박하준', '은', '은'), ('김하늘', '은', '은'), ('수지', '는', '는'), ('박하준', '이', '이'), ('수지', '이', '가'), ('박하준', '을', '을'),
                          ('수지', '을', '를'), ('박하준', '와', '과'), ('수지', '과', '와'), ('수지', '으로', '로'), ('김하늘', '으로', '로'), ('박하준', '로', '으로'),
                          ('수지', '이다', '다'), ('박하준', '다', '이다'), ('010-1234-5678', '은', '은'), ('A-12', '은', '는')):
        assert ioflow.fix_particle(word, p) == want, (word, p, ioflow.fix_particle(word, p))
    print('PRIVACY SELFTEST PASS')
    return 0


def cmd_enable(sess, args):
    p = settings.enable(enforce='--no-enforce' not in args, user=True)
    print(f'VAULT ENABLE ok: {p} (every hd call loads the privacy layer; if it cannot be loaded hd stops with PRIVACY ADDON NOT LOADED)')
    return 0


def cmd_disable(sess, args):
    if not (sys.__stdin__.isatty() and sys.__stdout__.isatty()):
        print('VAULT DISABLE refused: only you can switch the layer off, from a terminal.')
        V.audit('disable-refused')
        return 1
    V.audit('disable')
    print(f'VAULT DISABLE ok: {settings.disable()}')
    return 0


def cmd_status(sess, args):
    print(f'STATUS {"enabled" if settings.is_enabled() else "disabled"}, mode {settings.mode()}, vault backend {V.backend()}, '
          f'packs {", ".join(sess.det.meta)}, {len(sess.vault.data["entries"])} tags, {len(sess.det.kinds)} kinds')
    return 0
