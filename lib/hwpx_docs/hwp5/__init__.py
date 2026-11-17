"""hwp5: the binary .hwp format (HWP 5.0) with no Hangul: read, edit text in place, check the form, draw the pages.

Public interface (other packages use only these):
  edit.Doc(path)           .slots(), .labels(), .fill({key or label: text}) -> missing, .set(key, text),
                           .replace(old, new) -> count, .check(label, mark='☑'), .text(), .save(dst) -> dst
  guard.report(original, edited, forbid=(), require=(), max_unchanged=None, render_dir=None, out=print) -> fails
  tospec.read(path, out_json=None) -> spec dict      HWP -> the builder's spec (pictures saved next to out_json)
  render.pages(path, out_dir, backend='auto', dpi=96) -> [page files]   preview (own) or Hangul
  render.compare(before, after, out_dir, backend='auto') -> findings    page by page, before / after
  fmt.Package(path)        FileHeader, record streams, save through cfb.patch
Command: `hd hwp <sub>` (cli.py lists the subcommands).

Files: cfb.py (compound file: read, patch in place, build), fmt.py (FileHeader, records, paragraphs, the units of a
paragraph's text), docinfo.py (fonts, char / para shapes, border fills, styles, pictures), edit.py, guard.py,
tospec.py (HWP -> spec), render.py (page images and before / after comparison), info.py, tests.py (self-test on
documents it builds; `hd selftest --fixtures DIR` also runs every .hwp in DIR), rules.md (HW01-), coverage.md.
Depends on core (protect, tmpdir, build, textfit, registry) and, for pages, on the preview through
`registry.backend('render', 'preview')` and on `render.hwpcom` / `render.img` (Hangul pages, image comparison).
Password, distribution (배포용) and DRM documents are refused (core.protect, exit 4): nothing here decrypts.
"""
NOTICE = '본 제품은 한글과컴퓨터의 한글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다.'

COMMANDS = {
    'hwp': ('cli', [], '<sub> ...  .hwp (HWP 5.0) with no Hangul: info, text, slots, edit, guard, render, compare, '
                       'tospec, tohwpx'),
}


def selftest():
    from . import tests
    tests.selftest()
