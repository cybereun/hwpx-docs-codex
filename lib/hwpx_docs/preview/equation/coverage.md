# Coverage C13.13: equations in the preview (`lib/hwpx_docs/preview/equation/`)

Script commands, from the Hangul help and the equation file-format document. "drawn" = the preview draws it as vector shapes
and text; "text" = the preview shows the script as text and prints a warning line.

| id | commands | state | note |
|---|---|---|---|
| C13.13.01 | letters, digits, Hangul text, `+ - = < > ( ) [ ] / , .`, multi-character symbols (`-> <- <-> <= >= != == << >>`) | drawn | Latin letters italic, digits upright (E01, E09) |
| C13.13.02 | `over` `atop` `choose` `binom` | drawn | E03, E10 |
| C13.13.03 | `sqrt` `root n of` | drawn | E13 |
| C13.13.04 | `^` `_` `sup` `sub` `from` `to` `lsup` `lsub` | drawn | E02, E11 |
| C13.13.05 | `sum` `prod` `coprod` `union` `inter` `int` `oint` `dint` `tint` `odint` `otint` `lim` with limits | drawn | E12 |
| C13.13.06 | `left` `right` brackets: `( ) [ ] \| lbrace rbrace langle rangle lceil rceil lfloor rfloor` | drawn | E06, E14 |
| C13.13.07 | `matrix` `pmatrix` `bmatrix` `dmatrix` `cases` `pile` `lpile` `rpile` `eqalign` | drawn | E06, E15 |
| C13.13.08 | Greek letters, set / operator / logic / arrow / other symbols of the symbol tables | drawn | `symbols.py`; the glyph of a symbol the font lacks comes from the next browser font |
| C13.13.09 | accents `acute grave dot ddot hat check tilde bar vec dyad under arch`, `not`, `bigg`, `rel`, `buildrel` | drawn | E05, E17 |
| C13.13.10 | `rm` `it` `bold` `rmbold` `scale` `color`; blanks `~` and backtick; quotes; `#` line break | drawn | E04, E07, E16 |
| C13.13.11 | `ladder` `sladder` `longdiv` `phantom`, matrix column modes `col` `lcol` `rcol` | drawn | E08, E21-E23; the column mode syntax is confirmed by a Hangul page |
| C13.13.12 | an equation that is not a character (`treatAsChar="0"`): offset and text wrap | line | the reader keeps every equation as an inline run, so it is drawn at its anchor; a failing script is written as text with the warning `equation drawn as text` (E19). The size stored in `hp:sz` is not used: the preview lays the equation out itself |

## Fidelity against Hangul pages

2026-11-14, 27 samples (`fixtures/samples.json`), Hangul pages at 96 dpi in `fixtures/ref/`, one Hangul batch. `ink` = `hd img compare`
(percent of 4 px blocks with ink in one image only), `coarse` = 12 px blocks (layout, 3 mm). An equation page has very little ink, so
a shift of one glyph weighs much more than on a text page (text pages: mean ink 17.9). The layout numbers `M` in `layout.py` were
fitted to the ink boxes (width and height in pixels, mean error 6 px per sample, `fixtures/fidelity.json` keeps the table).

| sample | ink | coarse | | sample | ink | coarse |
|---|---|---|---|---|---|---|
| frac | 35.5 | 14.3 | | greek | 22.8 | 16.0 |
| sup | 25.0 | 0.0 | | accents | 52.1 | 7.7 |
| chem | 20.2 | 0.0 | | scripts | 46.0 | 4.2 |
| func | 30.4 | 0.0 | | nested | 45.0 | 19.4 |
| root | 30.3 | 3.8 | | piles | 66.1 | 40.0 |
| integral | 40.6 | 28.6 | | doc_limsum | 51.4 | 15.4 |
| integral_ft | 32.6 | 15.0 | | mixed14 | 57.2 | 8.3 |
| sum | 42.5 | 11.8 | | spaces | 14.3 | 0.0 |
| limit | 42.7 | 13.3 | | ladder | 49.6 | 20.0 |
| brackets | 43.0 | 12.5 | | sladder | 64.8 | 33.3 |
| bmatrix | 39.0 | 16.7 | | longdiv | 34.2 | 7.7 |
| matrices | 34.2 | 0.0 | | longdiv_blank | 34.2 | 7.7 |
| cases | 46.7 | 21.4 | | colmatrix | 52.3 | 24.1 |
| | | | | phantom | 35.1 | 18.2 |
| **mean** | **40.3** | **13.3** | | before the fit (first guesses) | 81.8 | 73.5 |

Open (largest differences): `piles` (Hangul puts the two rows of `eqalign` about 2 em apart and starts the first at the second row of
the `pile` next to it; one sample, not modelled), `sladder` and `ladder` (Hangul's rung and dot spacing), `accents`, `mixed14`,
`scripts`: glyph shapes (Hangul's italic letters are wider and lighter than the synthetic italic of `HancomEQN` in Edge) and
sub-pixel positions. The matrix column mode `matrix{col{..} rcol{..} lcol{..}}` is confirmed by the Hangul page (centred, right and
left aligned columns).

Job that made the references (hidden Hangul, one instance, security module registered): open each `fixtures/eq_<name>.hwpx`, save the page
image, save again as HWPX. Hangul keeps the stored size of the equation object (1 x 1 mm): `fixtures/sizes.json` shows that it does not
write back the size it draws, so the size is measured on the page image (rules E20).
