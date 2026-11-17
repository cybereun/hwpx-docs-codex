#!/usr/bin/env python3
"""check_gongmun.py - flag machine-checkable problems in a Korean official document.

Usage:
  python check_gongmun.py FILE [--register gongmun|general] [--require-end] [--internal]
  (FILE may be "-" for stdin, read as UTF-8.)
Self-test: python check_gongmun.py --selftest (runs the samples in test/).

Output, one line per finding:  <line>: <rule id> <text>
Exit code: 0 = no finding, 1 = findings.

Rule ids: N## = references/notation.md, I## = item symbols (structure.md section 2),
E## = 끝/붙임 marks (structure.md sections 3-4), W03 = long sentence, EN3 = sentence ending,
P/T/A/X### = rows of the tables in references/wording.md (only rows with check = Y).
Standard library only.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

WORDING = Path(__file__).resolve().parent.parent / "references" / "wording.md"
ROW = re.compile(
    r"^\|\s*([PTAX]\d{3})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(\w+)\s*\|\s*([YN])\s*\|\s*([^|]*?)\s*\|"
)
# 가..하, then 거..허 when a level has more than 14 items (시행규칙 제2조①)
HANGUL_SEQ = "가나다라마바사아자차카타파하거너더러머버서어저처커터퍼허"
HS = "[" + HANGUL_SEQ + "]"
DAYS = "월화수목금토일"  # datetime.weekday(): Monday = 0

# item symbol patterns, level 1..8 (structure.md section 2)
ITEM_PATTERNS = [
    (1, re.compile(r"^(\s*)(\d{1,2})\.\s+(?=\S)(?!\d{1,2}\.\s)")),
    (2, re.compile(r"^(\s*)(" + HS + r")\.\s+(?=\S)")),
    (3, re.compile(r"^(\s*)(\d{1,2})\)\s+(?=\S)")),
    (4, re.compile(r"^(\s*)(" + HS + r")\)\s+(?=\S)")),
    (5, re.compile(r"^(\s*)\((\d{1,2})\)\s+(?=\S)")),
    (6, re.compile(r"^(\s*)\((" + HS + r")\)\s+(?=\S)")),
    (7, re.compile(r"^(\s*)([①-⑳])\s*(?=\S)")),
    (8, re.compile(r"^(\s*)([㉮-㉻])\s*(?=\S)")),
]
SYMBOL_NAME = {1: "1.", 2: "가.", 3: "1)", 4: "가)", 5: "(1)", 6: "(가)", 7: "①", 8: "㉮"}


def load_word_rows(skip_groups):
    rows = []
    if not WORDING.exists():
        return rows
    for text in WORDING.read_text(encoding="utf-8").splitlines():
        m = ROW.match(text)
        if not m:
            continue
        rid, term, repl, group, check, src = m.groups()
        if check != "Y" or repl.strip() in ("–", "-", ""):
            continue
        if group in skip_groups:
            continue
        term = term.strip()
        # "re:<regex>" = regex term; else plain text. P/A/X terms are words, so they must
        # start a word (no Hangul or digit before them); T terms attach to the noun before.
        body = term[3:] if term.startswith("re:") else re.escape(term)
        if rid[0] in "PAX":
            body = r"(?<![가-힣0-9])" + body
        rows.append((rid, term[3:] if term.startswith("re:") else term, re.compile(body), repl.strip(), src.strip()))
    rows.sort(key=lambda r: -len(r[1]))  # longest term first
    return rows


def item_index(level, sym):
    if level in (1, 3, 5):
        return int(sym)
    if level in (2, 4, 6):
        return HANGUL_SEQ.index(sym) + 1
    if level == 7:
        return ord(sym) - 0x2460 + 1
    return ord(sym) - 0x326E + 1


def parse_item(line):
    for level, pat in ITEM_PATTERNS:
        m = pat.match(line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            return level, m.group(2), indent
    return None


def check_items(lines, out):
    stack = []  # entries: [level, last_index, count, first_line]

    def pop_to(level):
        while stack and stack[-1][0] > level:
            closed = stack.pop()
            if closed[2] == 1:
                out.append((closed[3], "I04", "single item at level %s: do not write an item symbol" % SYMBOL_NAME[closed[0]]))

    in_attach = False
    for n, line in lines:
        # 붙임 lines (structure.md A2) are numbered on their own; they are not body items
        if re.match(r"^\s*붙임", line):
            in_attach = True
        elif not line.strip():
            in_attach = False
        if in_attach:
            if END_MARK.search(line):
                in_attach = False
            continue
        item = parse_item(line)
        if not item:
            continue
        level, sym, indent = item
        idx = item_index(level, sym)
        want_indent = 2 * (level - 1)
        if indent != want_indent and "\t" not in line[: indent + 1]:
            out.append((n, "I03", "indent %d, expected %d for level %s (2타 per level)" % (indent, want_indent, SYMBOL_NAME[level])))
        if level == 1 and idx == 1:
            pop_to(0)
            while stack:
                closed = stack.pop()
                if closed[2] == 1:
                    out.append((closed[3], "I04", "single item at level %s: do not write an item symbol" % SYMBOL_NAME[closed[0]]))
            stack.append([1, 1, 1, n])
            continue
        if not stack:
            out.append((n, "I01", "list starts at level %s; the first level is 1." % SYMBOL_NAME[level]))
            stack.append([level, idx, 1, n])
            continue
        top = stack[-1][0]
        if level > top + 1:
            out.append((n, "I01", "level %s skips a level (previous level %s)" % (SYMBOL_NAME[level], SYMBOL_NAME[top])))
            stack.append([level, idx, 1, n])
            continue
        if level == top + 1:
            if idx != 1:
                out.append((n, "I02", "first item of level %s must be the first symbol, got %s" % (SYMBOL_NAME[level], sym)))
            stack.append([level, idx, 1, n])
            continue
        pop_to(level)
        if stack and stack[-1][0] == level:
            ent = stack[-1]
            if idx != ent[1] + 1:
                out.append((n, "I02", "item order at level %s: expected index %d, got %s" % (SYMBOL_NAME[level], ent[1] + 1, sym)))
            ent[1] = idx
            ent[2] += 1
        else:
            stack.append([level, idx, 1, n])
    pop_to(0)


DATE_KO = re.compile(r"(?<!\d)(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
DATE_ISO = re.compile(r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})(?![\d-])")
DATE_TIGHT = re.compile(r"(?<![\d.])(\d{4})\.(\d{1,2})\.(\d{1,2})\.?(?!\d)")
DATE_NOFINAL = re.compile(r"(?<![\d.])(\d{4})\. (\d{1,2})\. (\d{1,2})(?![\d.])")
DATE_ZERO = re.compile(r"(?<![\d.])\d{4}\. (?:0\d\. \d{1,2}|\d{1,2}\. 0\d)\.")
DATE_FULL_WD = re.compile(r"(?<![\d.])(\d{4})\. (\d{1,2})\. (\d{1,2})\.\s*\(([월화수목금토일])\)")
WEEKDAY_SPACE = re.compile(r"\.\s+\(([월화수목금토일])\)")
TIME_KO = re.compile(r"(오전|오후)\s*\d{1,2}\s*시|(?<!\d)\d{1,2}시(?![간가])(?:\s*\d{1,2}분)?")
TIME_1DIGIT = re.compile(r"(?<![\d:])\d:[0-5]\d(?![\d:])")
# ponytail: a one-digit "h:mm" is reported only on a line that talks about time; a ratio
# such as "축척 1:50" looks the same. Add a ratio word list if it still misfires.
TIME_CONTEXT = re.compile(r"일시|시간|시각|부터|까지|~|오전|오후")
TIME_SPACED = re.compile(r"\d{1,2} : \d{2}")
RANGE_SPACE = re.compile(r"(?<=[\d.])\s+~|~\s+(?=\d)")
# `금` as the money mark starts a word; `지원금 1,000원` is a plain noun + amount
MONEY_SPACE = re.compile(r"(?<![가-힣])금\s+\d")
MONEY_UNIT = re.compile(r"(?<![가-힣])금\d[\d,]*[만억천]")
MONEY_NOHANGUL = re.compile(r"(?<![가-힣])금\d[\d,]*원(?!\s*\(금)")
COLON_SPACE = re.compile(r"(?<=[가-힣])\s+:\s")
COLON_TIGHT = re.compile(r"(?<=[가-힣]):(?=[^\s/])")
ATTACH_COLON = re.compile(r"^\s*붙임\s*:")
END_MARK = re.compile(r"(?:^|\s)끝\.\s*$")
END_SPACING = re.compile(r"\S ?끝\.\s*$")
END_NO_PERIOD = re.compile(r"\s끝\s*$")
END_EMPTY = re.compile(r"이하\s*빈칸")
ENDING_BAD = re.compile(r"(바람|요망|할 것)\.?\s*$")


def check_notation(lines, out):
    for n, line in lines:
        for m in DATE_KO.finditer(line):
            y, mo, d = (int(x) for x in m.groups())
            out.append((n, "N02", "date `%s` -> `%d. %d. %d.`" % (m.group(0), y, mo, d)))
        for m in DATE_ISO.finditer(line):
            y, mo, d = (int(x) for x in m.groups())
            out.append((n, "N02", "date `%s` -> `%d. %d. %d.`" % (m.group(0), y, mo, d)))
        for m in DATE_TIGHT.finditer(line):
            y, mo, d = m.groups()
            out.append((n, "N02", "date `%s` needs a space after each period: `%s. %d. %d.`" % (m.group(0), y, int(mo), int(d))))
        for m in DATE_NOFINAL.finditer(line):
            out.append((n, "N02", "date `%s` needs the last period: `%s.`" % (m.group(0), m.group(0))))
        for m in DATE_ZERO.finditer(line):
            out.append((n, "N02", "date `%s` has a leading zero in month or day" % m.group(0)))
        for m in WEEKDAY_SPACE.finditer(line):
            out.append((n, "N03", "weekday: no space before the parenthesis (`2026. 11. 14.(토)`)"))
        for m in DATE_FULL_WD.finditer(line):
            y, mo, d, wd = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
            try:
                real = DAYS[datetime.date(y, mo, d).weekday()]
            except ValueError:
                out.append((n, "N02", "date `%d. %d. %d.` does not exist" % (y, mo, d)))
                continue
            if real != wd:
                out.append((n, "N03", "weekday of %d. %d. %d. is %s, not %s" % (y, mo, d, real, wd)))
        for m in TIME_KO.finditer(line):
            out.append((n, "N04", "time `%s` -> 24-hour `HH:MM` (for example `14:00`)" % m.group(0)))
        if TIME_CONTEXT.search(line):
            for m in TIME_1DIGIT.finditer(line):
                out.append((n, "N04", "time `%s` -> two-digit hour (for example `07:09`)" % m.group(0)))
        for m in TIME_SPACED.finditer(line):
            out.append((n, "N04", "time `%s`: no spaces around the colon" % m.group(0)))
        for m in RANGE_SPACE.finditer(line):
            out.append((n, "N06", "range mark `~` is attached to both sides"))
        if MONEY_SPACE.search(line):
            out.append((n, "N07", "money: no space after `금` (`금113,560원(금일십일만삼천오백육십원)`)"))
        if MONEY_UNIT.search(line):
            out.append((n, "N07", "money: write Arabic digits only after `금` (no 만, 억, 천)"))
        for m in MONEY_NOHANGUL.finditer(line):
            out.append((n, "N07", "money `%s` needs the Hangul amount in parentheses `(금...원)`" % m.group(0)))
        if COLON_SPACE.search(line):
            out.append((n, "N08", "colon: no space before it (`일시: ...`)"))
        if COLON_TIGHT.search(line):
            out.append((n, "N08", "colon: one space after it (`일시: ...`)"))


def check_ending_marks(lines, out, require_end):
    texts = [t for _, t in lines]
    looks_official = require_end or any(re.match(r"^\s*(수신|제목|붙임)\b", t) for t in texts)
    last_nonblank = None
    end_lines = []
    has_empty_table_mark = False
    for n, t in lines:
        if t.strip():
            last_nonblank = n
        if END_MARK.search(t):
            end_lines.append(n)
        if END_EMPTY.search(t):
            has_empty_table_mark = True
        if ATTACH_COLON.match(t):
            out.append((n, "E06", "no colon after 붙임"))
        if END_SPACING.search(t):
            out.append((n, "E03", "`끝.` goes 2 spaces after the last character"))
        if END_NO_PERIOD.search(t) and not END_MARK.search(t):
            out.append((n, "E04", "write `끝.` with a period (편람 examples)"))
    if looks_official and not end_lines and not has_empty_table_mark:
        out.append((last_nonblank or 1, "E01", "missing `끝.` mark (or `이하 빈칸` when a table ends early)"))
    if len(end_lines) > 1:
        for n in end_lines[1:]:
            out.append((n, "E05", "more than one `끝.` mark"))


def strip_markup(text):
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+|#+\s+)", "", text)
    return text.replace("**", "").replace("`", "")


def check_sentences(lines, out, internal):
    for n, line in lines:
        if line.lstrip().startswith("|"):
            continue
        text = strip_markup(line)
        for sentence in re.split(r"(?<=[.?!])\s+", text):
            if len(sentence.strip()) > 100:
                out.append((n, "W03", "sentence has %d characters (convention: split over 100)" % len(sentence.strip())))
        if not internal and ENDING_BAD.search(text):
            out.append((n, "EN3", "ending `~바람/~요망/~할 것`: for other offices or the public use `~하시기 바랍니다`"))


def check_words(lines, out, rows):
    for n, raw_line in lines:
        # the Hangul amount of a money figure (`(금일십일만...원)`) is not the word 금일
        line = re.sub(r"\(금[가-힣]+원\)", lambda m: " " * len(m.group(0)), raw_line)
        taken = []
        for rid, term, pat, repl, src in rows:
            for m in pat.finditer(line):
                i, j = m.span()
                if not any(i < b and a < j for a, b in taken):
                    taken.append((i, j))
                    out.append((n, rid, "`%s` -> %s (%s)" % (m.group(0), repl, src)))


def check_text(raw, register="gongmun", require_end=False, internal=False):
    """Return the sorted, unique findings [(line, rule id, text)] for one document."""
    lines, fenced = [], False
    for n, line in enumerate(raw.splitlines(), 1):
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            lines.append((n, line.rstrip("\n")))

    out = []
    general = register == "general"
    if not general:
        check_items(lines, out)
        check_notation(lines, out)
        check_ending_marks(lines, out, require_end)
        check_sentences(lines, out, internal)
    check_words(lines, out, load_word_rows({"FO", "TG"} if general else set()))
    return sorted(set(out), key=lambda x: (x[0], x[1], x[2]))


def selftest():
    """Each sample in test/ must give exactly the expected set of rule ids."""
    test = Path(__file__).resolve().parent / "test"
    expected = {
        "sample_good.md": set(),
        "sample_edge.md": set(),
        "sample_bad_end.md": {"E03", "E05"},
        "sample_bad.md": {"A011", "A016", "E01", "E06", "EN3", "I01", "I02", "I03", "I04", "N02", "N03",
                          "N04", "N06", "N07", "N08", "P004", "P005", "P008", "P012", "P014", "P027",
                          "P038", "P055", "P056", "P325", "T003", "T017", "T020", "T036", "W03", "X002"},
    }
    failed = 0
    for name, want in expected.items():
        got = {rid for _, rid, _ in check_text((test / name).read_text(encoding="utf-8"))}
        status = "ok" if got == want else "FAIL missing=%s extra=%s" % (sorted(want - got), sorted(got - want))
        failed += status != "ok"
        print("%s: %s" % (name, status))
    return 1 if failed else 0


def main():
    for stream in (sys.stdout, sys.stdin):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if sys.argv[1:] == ["--selftest"]:
        return selftest()

    ap = argparse.ArgumentParser(description="Check a Korean official document (공문).")
    ap.add_argument("file", help="Markdown or text file, or - for stdin")
    ap.add_argument("--register", choices=["gongmun", "general"], default="gongmun",
                    help="general = skip format checks (date, time, money, items, 끝.), loanword rows (FO) "
                         "and 공문-only translation rows (TG)")
    ap.add_argument("--require-end", action="store_true", help="always require the 끝. mark")
    ap.add_argument("--internal", action="store_true",
                    help="internal 개조식 report: do not report ~바람/~요망/~할 것 endings (EN3)")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
    found = check_text(raw, args.register, args.require_end, args.internal)
    for n, rid, text in found:
        print("%d: %s %s" % (n, rid, text))
    print("%d finding(s)" % len(found), file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
