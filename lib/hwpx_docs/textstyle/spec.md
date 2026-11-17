# Text style spec keys

```json
{"named_styles": {
   "본문 가":  {"size": 11, "line": 170, "left": 5, "eng": "Mybody", "next": "본문 가"},
   "제목 나":  {"size": 16, "bold": true, "align": "center", "next": "본문 가"},
   "강조":     {"type": "char", "bold": true, "color": "#C00000"}},
 "body": [
   {"style": "제목 나", "p": "제목"},
   {"style": "본문 가", "p": ["가나 ", {"t": "강조", "style": "강조"}, " 다"]},
   {"style": "개요 1", "p": "built-in names need no named_styles"},
   {"p": "항목\t1,234.5", "tabs": [{"pos": 40, "type": "left", "leader": "dot"},
                                 {"pos": 100, "type": "decimal"}]},
   {"p": "x\ty", "tabs": {"stops": [{"pos": 20}], "auto_right": true}}]}
```
`named_styles`: the style's props are the paragraph keys (`align`, `left`, `line`, ...) and the character keys (`size`,
`bold`, ...) in one flat dict; `type` is `para` (default) or `char`; `eng` the English name; `next` the name of the style
that Hangul applies to the paragraph after Enter (default: itself). `style` on a block, cell block or run: see
`rules.md` TS12. `tabs`: TS04. Positions are millimetres from the paragraph's text left; `leader` takes the line type
names of `core/units.py LINE_TYPES`.

## Drop cap, 덧말

```json
{"body": [
  {"dropcap": {"lines": 2, "font": "함초롬돋움", "color": "#C00000", "frame": "0.4mm solid #FF0000", "fill": "#FFFF00"},
   "p": "문단 첫 글자 장식"},
  {"p": ["앞 ", {"dutmal": {"main": "본말", "sub": "덧말", "pos": "top", "size": 50, "align": "center"}}, " 뒤"]}]}
```
`dropcap` on a block makes the first character of `p` the drop cap (`lines` 2, 3 or `"margin"`); `hd read` writes it as a run
item `{"dropcap": {"char": "문", "lines": 2}}` first in `p`, followed by the rest of the text. `dutmal`: `pos` top (default) or
bottom, `size` = sub text size in % (default 50), `align` center (default), left, right, justify, distribute.

## Picture bullet

```json
{"body": [{"bullet_image": "bullet.png", "p": "first"}, {"bullet_image": "bullet.png", "bullet": "●", "p": "second"}]}
```
`bullet_image` (PNG, JPG, BMP or GIF path relative to the spec file) makes a picture bullet; `bullet` stays its character
(default ●, what the preview prints), and a `bullet` alone is a character bullet. `hd read` writes the image next to the spec (rules.md TS22).
