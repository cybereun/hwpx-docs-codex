# Equation renderer: rules (Hangul equation script)

Rules E01-E23 of `lib/hwpx_docs/preview/equation/`. Evidence keys as in `docs/rules.md`: D = the public Hangul help pages and the equation
file-format document (revision 1.3), S = a sample made by Hangul, P = measured on Hangul's own page image (96 dpi), H = hand-set
(no Hangul page checks it, marked "open"). Samples: `fixtures/samples.json` (27 scripts), `fixtures/eq_<name>.hwpx` (builder output),
`fixtures/ref/eq_<name>_page1.png` (Hangul pages) and `fixtures/sizes.json` (the equation size after Hangul saved the files again).

## Grammar (parse.py)

| id | rule | evidence |
|---|---|---|
| E01 | Letters: a run of Latin letters is a command word when the whole run is one (`over`, `alpha`, `SUM`); a function name at the start of a run is split off (`logx` = `log` `x`); any other letter is an italic letter on its own. Inside a run no command is looked for (`Editor` has no `or`). Digits are upright; Hangul and other characters are upright text. | D:1.1.3; open: P |
| E02 | `^` `_` (and `sup` `sub`, `from` `to`) attach to the previous atom, also across spaces (`int _1 ^2`). The operand is a `{group}`, a quoted string, or the rest of the word up to a space, a backtick, a tilde, the next `^` `_`, a `{`, or a command word (`sum_n=1^N` has the lower limit `n=1`; `^3sqrt{..}` ends before `sqrt`). | D:2.3, 2.5; open: P |
| E03 | `over` `atop` `choose` `lsub` `lsup` take the word before and the word after (a word = atoms up to a space or a group): `a + b over c` is `a + (b/c)`, `a+b over c` is `(a+b)/c`. | D:1.2, 2.1 |
| E04 | Spaces and line ends only separate words; nothing is drawn for them (`Equation font test` shows `Equationfonttest`). `~` is a blank, backtick a quarter of it, `{ }` groups, `" "` quotes (a word of 9 characters or more), `#` is a line break, `&` aligns columns. | D:1.1.2 |
| E05 | `sqrt x`, `root n of x`, `hat x`, `bar x`, `not x`, `bigg x` take the next word or group. Accents: acute grave dot ddot hat check tilde bar vec dyad under arch. | D:1.2, 1.2.1 |
| E06 | `left X ... right Y` puts brackets that grow with the content around it; X, Y: `( ) [ ] \| lbrace rbrace langle rangle lceil rceil lfloor rfloor`. `matrix{a & b # c & d}` (and `pmatrix` `bmatrix` `dmatrix`), `cases{..}`, `pile` `lpile` `rpile`, `eqalign{a & b # ..}`: rows by `#`, columns by `&`. | D:1.2 |
| E07 | `rm` roman, `it` italic, `bold`, `rmbold` change the style of the rest of the group; `scale n` sets the size to n percent; `color {r,g,b} {body}` colours one operand. | D:1.1.1 |
| E08 | `ladder{2&12&28 # 2&6&14 # 3&7&}`, `sladder{..}`, `longdiv{divisor}{quotient}{dividend # row # ..}`, `phantom{x}` (room, no ink) and the column mode of matrices `matrix{col{a#b} lcol{c#d} rcol{e#f}}` (one group per column, `col` centred, `lcol` left, `rcol` right) take a group; the shapes are in E21-E23. | D:1.2 (pictures); open (column mode: syntax read from the help text) |

## Metrics (layout.py, constants in `M`)

All sizes are fractions of the font size of the equation (`baseUnit`). The numbers were fitted to the ink boxes of the 27 Hangul pages
(`fixtures/ref`, width and height within 6 px on average, table in `coverage.md`); "one sample" marks a value that rests on a single page.

| id | rule | evidence |
|---|---|---|
| E09 | The equation font is `HancomEQN` (installed with Hangul); Latin letters are drawn italic, digits and functions upright, Greek letters are italic glyphs of the font itself. Without the font the browser takes `Cambria Math` or `Times New Roman`. Operators (`+ = < >`) have a 1 em advance in the font; that is the room around them. | S:equation_add_B; P |
| E10 | Fraction: the bar is 0.04 em thick on the axis (0.25 em above the baseline); numerator and denominator keep the size of the text and sit 0.27 em from the bar; the bar overhangs 0.10 em on each side. | P:frac nested brackets limit |
| E11 | Sub and superscripts are drawn at 0.65 of the size (limits of a big operator 0.55 / 0.65: `limit_scale`); a superscript rises at least 0.42 em, a subscript falls at least 0.20 em; both on one base keep 0.15 em apart. | P:sup scripts; one sample for the rise |
| E12 | Big operators centred on the axis: `sum` `prod` `coprod` 1.5 times, `union` `inter` 1.25 times, integrals 2.15 times the size (the integral sign has 0.21 sign sizes of room on its left); the word `lim` is 1.2 times. `sum` `prod` `union` `inter` `lim` put the limits above and below, integrals at the right side. | P:integral sum limit doc_limsum |
| E13 | Radical: a tick, a long stroke and a bar over the radicand (0.15 em above it); `root n of x` puts the index (0.6 size) over the tick. | P:root (width within 6 px) |
| E14 | Brackets of `left` `right`, `matrix` and `cases` are drawn as paths that stretch with the content (height of the body plus 0.05 em); width 0.30 em. | P:brackets cases bmatrix |
| E15 | Matrix: columns centred, 0.30 em apart; rows at least 1.05 em high plus 0.30 em; the matrix is centred on the axis. `cases` left-aligns the cells; `eqalign` right-aligns the first column and left-aligns the second with no gap. `pile` rows are 1.05 em high plus 0.10 em. Column mode: `col` centred, `lcol` left, `rcol` right (confirmed). | P:bmatrix matrices cases piles colmatrix |
| E16 | Operators: a relation (`= < > ->` ...) has 0.15 em more room on each side than the font gives it, a binary operator (`+ - times`) 0.10 em; `~` is 0.5 em, backtick 0.125 em. | P:sup chem func greek scripts; one sample for the blank |
| E17 | Accents sit 0.10 em over the body; `bar` `vec` `dyad` are lines as wide as the body, `hat` `check` `tilde` `arch` widen with the body. | D:1.2.1 (pictures); P:accents (width within 10 px) |
| E18 | Vertical place: the top of the equation is 0.75 em below the top of its line, whatever its height (10 pt: 10 px, 14 pt: 15 px, 27 samples within 3 px); the line grows with the equation. | P:all samples |
| E19 | A script that fails (too deep, an internal error) is written as text and the page output prints `WARN preview: equation drawn as text`. Every command of the Hangul help is drawn, so this is a safety net only. | - |
| E20 | The builder writes `hp:equation` with `baseLine` 66 and size 1 x 1 mm unless the spec gives `w`, `h`. Hangul draws the equation at its real size and saves the stored size back unchanged (`fixtures/sizes.json`: 283 hu = 1 mm for all 27), so the preview ignores the stored size. | S:27 samples saved again |
| E21 | `ladder`: first column = divisors (right-aligned), then number columns (right-aligned). Every row but the last has a rung (a line under the numbers) and one vertical line runs through them. The last row has no divisor: its first cell stands in the first number column. `sladder`: the third column is the remainder, written after a row of dots; the rungs run under the first number column only. Rows are 0.5 em apart (plus the digit height), columns 0.20 em. | D:1.2 (picture); P:ladder sladder (shape right, spacing open) |
| E22 | `longdiv{6}{422}{2532#24#13#12#12#12#0}`: `6)2532` with a bar over the dividend, the quotient right-aligned over it, then the steps in digit columns (rows 1.12 em apart), a line under every subtrahend (rows 1, 3, 5 ...). Rows without blanks are placed by the long-division rule: the first subtrahend starts at the first digit, a remainder ends one column right of the subtrahend above (at most the last digit), a subtrahend ends where the remainder above ends. A row with a leading `~` is placed as written, one blank = one digit width; both forms give the same page. | D:1.2 (picture); P:longdiv longdiv_blank (Hangul draws the two forms the same) |
| E23 | `phantom{x}` takes the room of `x` and draws nothing (a retired Hangul 97 command). | D:1.1 |
