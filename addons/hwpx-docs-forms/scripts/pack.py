"""Forms pack tool (format: docs/forms-pack.md of the hwpx-docs repository). Standard library only.

  python pack.py apply <spec.json> <pack dir> -o <out.json> [--with opt1,opt2]   pack values + parts -> an ordinary spec
  python pack.py list <pack dir>                                                  rules with evidence
  python pack.py check <pack dir>                                                 manifest, evidence rule, parts
  python pack.py selftest

`apply` writes a spec that `hd build` takes. The pack never changes a value that the spec sets itself.
"""
import copy
import json
import os
import re
import sys
import tempfile

MERGE_KEYS = ('page', 'defaults', 'styles', 'tokens')
VAR = re.compile(r'\$\{([A-Za-z0-9_.-]+)\}')
DEPTH = 8
MAX_EXPANSIONS = 5000        # part references expanded in one apply(); the biggest real form needs a few dozen


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def deep_merge(base, over):
    """`over` wins, key by key (objects merge, everything else is replaced)."""
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def subst(x, env):
    if isinstance(x, str):
        m = VAR.fullmatch(x)
        if m:
            return copy.deepcopy(lookup(m.group(1), env))
        return VAR.sub(lambda m: str(lookup(m.group(1), env)), x.replace('$${', '\0')).replace('\0', '${')
    if isinstance(x, list):
        return [subst(i, env) for i in x]
    if isinstance(x, dict):
        return {k: subst(v, env) for k, v in x.items()}
    return x


def lookup(name, env):
    if name not in env:
        raise ValueError(f'unknown name ${{{name}}} (known: {", ".join(sorted(env)) or "none"})')
    return env[name]


def expand(blocks, parts, tokens, depth=0, budget=None):
    """Replace every {"part": name, "args": {...}} in lists (at any depth) by the body of that part.
    `budget` counts all part expansions of one apply(): a pack can nest 8 levels deep and still name a part many times per level,
    so the depth limit alone does not bound the size (8 levels of 100 references = 10^16 blocks)."""
    budget = [0] if budget is None else budget
    if depth > DEPTH:
        raise ValueError(f'parts nest deeper than {DEPTH}')
    if isinstance(blocks, list):
        out = []
        for b in blocks:
            if isinstance(b, dict) and 'part' in b:
                budget[0] += 1
                if budget[0] > MAX_EXPANSIONS:
                    raise ValueError(f'more than {MAX_EXPANSIONS} part references in one document (a pack that expands to this many blocks is refused)')
                name = b['part']
                if name not in parts:
                    raise ValueError(f'unknown part "{name}" (pack has: {", ".join(parts) or "none"})')
                spec = parts[name]
                env = dict(tokens)
                for p, default in spec.get('params', {}).items():
                    if p not in b.get('args', {}) and default is None:
                        raise ValueError(f'part "{name}" needs the argument "{p}"')
                    env[p] = b.get('args', {}).get(p, default)
                unknown = set(b.get('args', {})) - set(spec.get('params', {}))
                if unknown:
                    raise ValueError(f'part "{name}" has no parameter {", ".join(sorted(unknown))}')
                body = subst(spec['body'], env)
                out.extend(expand(body if isinstance(body, list) else [body], parts, tokens, depth + 1, budget))
            else:
                out.append(expand(b, parts, tokens, depth, budget))
        return out
    if isinstance(blocks, dict):
        return {k: expand(v, parts, tokens, depth, budget) for k, v in blocks.items()}
    return blocks


def picture_paths(x, where, bad):
    """A pack must not name a picture file outside the folder of the spec: `src` and `image` values that are absolute (a drive, a UNC name, a leading
    slash) or contain a `..` part are collected in `bad`. The builder would otherwise read that file into the document."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in ('src', 'image') and isinstance(v, str):
                parts_ = re.split(r'[\\/]', v)
                if os.path.isabs(v) or v.startswith(('/', chr(92))) or re.match(r'^[A-Za-z]:', v) or '..' in parts_:
                    bad.append(f'{where}: picture path "{v}" is absolute or leaves the folder')
            else:
                picture_paths(v, where, bad)
    elif isinstance(x, list):
        for v in x:
            picture_paths(v, where, bad)
    return bad


def apply(spec, pack_dir, with_=()):
    preset = load(os.path.join(pack_dir, 'preset.json'))
    parts_path = os.path.join(pack_dir, 'parts.json')
    parts = load(parts_path) if os.path.isfile(parts_path) else {}
    bad = picture_paths(preset, 'preset.json', picture_paths(parts, 'parts.json', []))
    if bad:
        raise ValueError('; '.join(bad[:3]))
    base = {k: preset.get(k, {}) for k in MERGE_KEYS}
    for name in with_:
        if name not in preset.get('optional', {}):
            raise ValueError(f'optional value "{name}" is not in the pack (has: {", ".join(preset.get("optional", {})) or "none"})')
        base = deep_merge(base, preset['optional'][name])
    tokens = deep_merge(base.get('tokens', {}), spec.get('tokens', {}))
    out = deep_merge({k: base[k] for k in ('page', 'defaults', 'styles')}, {k: spec[k] for k in ('page', 'defaults', 'styles') if k in spec})
    out.update({k: v for k, v in spec.items() if k not in MERGE_KEYS})
    out = {k: v for k, v in out.items() if v != {}}
    out = expand(out, parts, tokens)
    return subst_tokens(out, tokens)


def subst_tokens(x, tokens):
    """${token} left in the spec (outside parts) -> the token value."""
    return subst(x, tokens)


def used_parts(x, acc):
    if isinstance(x, dict):
        if 'part' in x:
            acc.add(x['part'])
        for v in x.values():
            used_parts(v, acc)
    elif isinstance(x, list):
        for v in x:
            used_parts(v, acc)
    return acc


def dig(obj, path):
    for k in path.split('.'):
        if not isinstance(obj, dict) or k not in obj:
            return KeyError
        obj = obj[k]
    return obj


def evidence(r):
    m = re.fullmatch(r'(\d+)/(\d+)', str(r.get('evidence', '')))
    if not m or int(m.group(2)) == 0 or int(m.group(1)) > int(m.group(2)):
        return None
    return int(m.group(1)), int(m.group(2))


def list_rules(pack_dir):
    man = load(os.path.join(pack_dir, 'pack.json'))
    for r in man.get('rules', []):
        print(f'{r["id"]} {json.dumps(r.get("value"), ensure_ascii=False)} {r.get("evidence")} {r.get("status")}')
    print(f'PACK {man["name"]} {len(man.get("rules", []))} rules')


def check(pack_dir):
    problems = []
    man = load(os.path.join(pack_dir, 'pack.json'))
    preset = load(os.path.join(pack_dir, 'preset.json'))
    pp = os.path.join(pack_dir, 'parts.json')
    parts = load(pp) if os.path.isfile(pp) else {}
    for r in man.get('rules', []):
        ev = evidence(r)
        if ev is None:
            problems.append(f'rule {r.get("id")}: evidence "{r.get("evidence")}" is not n/N')
        elif r.get('status') == 'default' and ev[0] * 2 < ev[1]:
            problems.append(f'rule {r["id"]}: default rule with {ev[0]}/{ev[1]} (< half): make it optional or remove it')
        if r.get('path') and dig(preset, r['path']) != r.get('value'):
            problems.append(f'rule {r["id"]}: preset.json {r["path"]} is {dig(preset, r["path"])!r}, manifest says {r.get("value")!r}')
        if r['id'].startswith('part.') and r['id'][5:] not in parts:
            problems.append(f'rule {r["id"]}: part "{r["id"][5:]}" is not in parts.json')
    inner = used_parts(parts, set())
    for u in inner - set(parts):
        problems.append(f'parts.json uses the unknown part "{u}"')
    for p in problems:
        print('PACK PROBLEM', p)
    if not problems:
        print('PACK OK', man['name'])
    return 1 if problems else 0


def selftest():
    with tempfile.TemporaryDirectory() as d:
        json.dump({'page': {'size': 'A4', 'margin': {'left': 20, 'right': 20}}, 'styles': {'label': {'bold': True}},
                   'tokens': {'label_fill': '#F2F2F2', 'line_thin': '0.12mm solid #000000'},
                   'optional': {'tight': {'page': {'margin': {'top': 10}}}}}, open(os.path.join(d, 'preset.json'), 'w'))
        json.dump({'to-address': {'params': {'who': None, 'tail': '귀하'}, 'body': [{'p': '${who} ${tail}', 'align': 'left'}]},
                   'sign': {'params': {}, 'body': [{'part': 'to-address', 'args': {'who': '○○○'}},
                                                   {'table': {'border': '${line_thin}', 'rows': [[{'p': 'x', 'fill': '${label_fill}'}]]}}]}},
                  open(os.path.join(d, 'parts.json'), 'w'))
        json.dump({'name': 't', 'rules': [{'id': 'page.size', 'path': 'page.size', 'value': 'A4', 'evidence': '3/4', 'status': 'default'},
                                          {'id': 'part.sign', 'evidence': '5/10', 'status': 'default'}]}, open(os.path.join(d, 'pack.json'), 'w'))
        spec = {'page': {'margin': {'left': 25}}, 'body': [{'part': 'sign'}, {'part': 'to-address', 'args': {'who': '홍길동', 'tail': '님'}}]}
        out = apply(spec, d, ['tight'])
        assert out['page'] == {'size': 'A4', 'margin': {'left': 25, 'right': 20, 'top': 10}}, out['page']
        assert out['body'][0] == {'p': '○○○ 귀하', 'align': 'left'}
        assert out['body'][1]['table']['border'] == '0.12mm solid #000000'
        assert out['body'][1]['table']['rows'][0][0]['fill'] == '#F2F2F2'
        assert out['body'][2]['p'] == '홍길동 님'
        assert check(d) == 0
        for bad in ({'body': [{'part': 'to-address'}]}, {'body': [{'part': 'nope'}]},
                    {'body': [{'p': '${zzz}'}]}, {'body': [{'part': 'sign', 'args': {'x': 1}}]}):
            try:
                apply(bad, d)
            except ValueError:
                continue
            raise AssertionError(f'no error for {bad}')
        man = load(os.path.join(d, 'pack.json'))
        man['rules'][0]['evidence'] = '1/4'
        json.dump(man, open(os.path.join(d, 'pack.json'), 'w'))
        assert check(d) == 1
        # a pack that names an absolute or `..` picture is refused; a pack that expands without limit is refused
        for bad_part in ({'p1': {'params': {}, 'body': [{'pic': {'src': 'C:/secret/a.png'}}]}}, {'p1': {'params': {}, 'body': [{'pic': {'src': '../x.png'}}]}},
                         {'p1': {'params': {}, 'body': [{'pic': {'src': '/etc/x.png'}}]}}):
            json.dump(bad_part, open(os.path.join(d, 'parts.json'), 'w'))
            try:
                apply({'body': [{'part': 'p1'}]}, d)
            except ValueError as e:
                assert 'picture path' in str(e), e
            else:
                raise AssertionError('no error for a bad picture path')
        json.dump({'a': {'params': {}, 'body': [{'part': 'b'}] * 100}, 'b': {'params': {}, 'body': [{'part': 'c'}] * 100}, 'c': {'params': {}, 'body': [{'p': 'x'}]}},
                  open(os.path.join(d, 'parts.json'), 'w'))
        try:
            apply({'body': [{'part': 'a'}]}, d)
        except ValueError as e:
            assert 'part references' in str(e), e
        else:
            raise AssertionError('no error for an expansion bomb')
    print('PACK SELFTEST PASS')


def main(args):
    if not args:
        print(__doc__)
        return 2
    cmd = args[0]
    try:
        if cmd == 'apply':
            out = args[args.index('-o') + 1]
            with_ = args[args.index('--with') + 1].split(',') if '--with' in args else []
            res = apply(load(args[1]), args[2], with_)
            with open(out, 'w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False, indent=1)
            print('SPEC WRITTEN', out)
        elif cmd == 'list':
            list_rules(args[1])
        elif cmd == 'check':
            return check(args[1])
        elif cmd == 'selftest':
            selftest()
        else:
            print(__doc__)
            return 2
    except (ValueError, OSError, KeyError, IndexError) as e:
        print('PACK ERROR', e, file=sys.stderr)
        return 3
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
