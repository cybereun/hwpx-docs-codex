"""hd pagefit: pages that read without turning back, and look full (no Hangul needed: the page layout of the preview + Hangul's rules).

  hd pagefit check <in.hwpx|spec.json> [--profile NAME|PATH] [--fill 85] [--last-lines 3] [--min-rows 3] [--weak]
  hd pagefit fix <in.hwpx|spec.json> <out.hwpx|out.json> [--profile NAME|PATH] [--fill 85] [--break-fill 70] [--max-extra 6]
        [--max-shrink 3] [--last-lines 3] [--min-rows 3] [--section-ratio 0.4] [--list-ratio 0.5] [--safety 1.5] [--safety-flow 8]
  hd pagefit profiles [NAME|PATH]       list the profiles, or print one in full (every key, as it is used)

The profile is the style: what is looked for and what is changed. With no `--profile` it is `minimal` (the first version: a heading keeps
with the next paragraph, no single lines, a table cut after its header row moves, forced breaks after a mostly empty page go, a short last
page is pulled back, free space goes into paragraph spacing). `--profile readable` also keeps the reading units whole (heading + first
content, item + sub items, table or figure with caption / introduction / notes, summary box, 붙임, last paragraph + 끝. + 결문; short
sections and numbered lists too when no page gets emptier), cuts a long table between rows with the header repeated and 3 rows at least in
each part, and looks for a sentence that points at a table on another page, a footnote that goes on, a pointer to a page number. Your own
profile is a JSON file (`--profile my.json`, format in profile.py and rules.md PF22). The options override single numbers of the profile.
`check` exits with 1 when it finds something; `fix` prints before, the changes and after, and writes a spec (.json) or a document (.hwpx,
built from the fixed spec). Text size, text and order of the blocks never change.
"""
import json
import sys

from . import check as ck
from . import model
from . import profile as prof_mod


def _opt(argv, name, default, cast=float):
    if name in argv:
        i = argv.index(name)
        v = cast(argv[i + 1])
        del argv[i:i + 2]
        return v
    return default


def main(argv):
    argv = list(argv)
    prof = _opt(argv, '--profile', None, str)
    kw = dict(fill=_opt(argv, '--fill', None), last_lines=_opt(argv, '--last-lines', None, int), min_rows=_opt(argv, '--min-rows', None, int),
              break_fill=_opt(argv, '--break-fill', None), max_extra=_opt(argv, '--max-extra', None), max_shrink=_opt(argv, '--max-shrink', None),
              safety=_opt(argv, '--safety', None), safety_flow=_opt(argv, '--safety-flow', None),
              section_ratio=_opt(argv, '--section-ratio', None), list_ratio=_opt(argv, '--list-ratio', None))
    weak = '--weak' in argv
    argv = [a for a in argv if a != '--weak']
    try:
        if argv[:1] == ['profiles']:
            if len(argv) == 1:
                for name in prof_mod.builtin():
                    print(f'{name}: {prof_mod.load(name)["description"]}')
                return 0
            print(json.dumps(prof_mod.load(argv[1]), ensure_ascii=False, indent=1))
            return 0
        P = prof_mod.load(prof if prof is not None else 'minimal', **kw)
        if argv[:1] == ['check'] and len(argv) == 2:
            spec, pic = model.load(argv[1])
            found, pgs = ck.check(spec, pic, weak=True if weak else None, profile=P)
            print('\n'.join(ck.report(found, pgs, P['check']['fill'])))
            return 1 if any(f.kind not in ('skipped', 'pageref') for f in found) else 0
        if argv[:1] == ['fix'] and len(argv) == 3:
            from . import fix
            spec, pic = model.load(argv[1])
            found, pgs = ck.check(spec, pic, profile=P)
            print(f'=== 프로필 {P["name"]} / 고치기 전 ===\n' + '\n'.join(ck.report(found, pgs, P['check']['fill'])))
            log = fix.fix(spec, pic, profile=P)
            print('=== 바꾼 내용 ===\n' + ('\n'.join(log) if log else '(바꿀 것이 없음)'))
            found, pgs = ck.check(spec, pic, profile=P)
            print('=== 고친 뒤 ===\n' + '\n'.join(ck.report(found, pgs, P['check']['fill'])))
            out = argv[2]
            if out.lower().endswith('.json'):
                json.dump(spec, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            else:
                from ..core import build
                build.write(spec, out, pic)
            print('WRITTEN', out)
            return 1 if any(f.kind not in ('skipped', 'pageref') for f in found) else 0
    except ValueError as e:
        print('ERROR', e)
        return 2
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
