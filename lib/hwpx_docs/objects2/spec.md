# Spec keys of the objects2 package

Lengths in mm. `hd build` and `core.read` use the same keys (round trip). Rules: `rules.md` (OB01-OB20).

## Picture (`{"pic": {...}}`, a run item or a block; keys added to the core keys `src`, `w`, `h`, `inline`, `pos`, `wrap`, `side`)

| key | value | XML |
|---|---|---|
| `bright`, `contrast` | -100 ... 100 | `hc:img bright`, `contrast` |
| `effect` | `real` (default), `gray`, `bw` | `hc:img effect` REAL_PIC, GRAY_SCALE, BLACK_WHITE |
| `crop` | [left, top, right, bottom] in % of the picture | `hp:imgClip` (picture units) |
| `border` | line string `"0.35mm dot #FF0000"` | `hp:lineShape` |
| `caption` | string, or {`text`, `label` ("그림"), `number` (true), `side` bottom, `gap`, `width`} | `hp:caption` |
| `side` | `both_sides`, `left_only`, `right_only`, `largest_only` | `textFlow` |
| `pos` (floating) | {`x`, `y`, `rel` paper\|page\|para, `hrel` paper\|page\|column\|para, `valign`, `halign`, `flow`, `overlap`} | `hp:pos` |

## Drawing object (rect, ellipse, line) in `shapes`

The core keys (`type`, `x`, `y`, `w`, `h`, `rel`, `line`, `fill`, `wrap`, `text`, ...) and: `hrel`, `halign` (left center right inside outside), `vpos` (top center bottom inside outside; not `valign`, which is the text inside a text box), `flow`, `overlap`, `side`, `caption` (as above, `number` false).

## Object block (`{"object": {...}}`)

Common: `kind`, `w`, `h`, `inline` (default true: on the text line; false: floating with `pos`, `wrap` (default square), `side`), `line` (`"0.12mm solid #000000"` or `none`), `fill`, `caption`.

| kind | keys |
|---|---|
| `polygon` | `points` [[x, y], ...], `closed` (default true) |
| `curve` | `segs` [[`line`\|`curve`, x1, y1, x2, y2], ...]; three `curve` in a row = one cubic Bezier |
| `connector` | `type` straight\|elbow\|arc, `arrow` none\|end\|both, `from` [x, y], `to` [x, y], `from_ref` / `to_ref` {id, idx} |
| `textart` | `text`, `shape` (one of `shapes.SHAPES`, default WAVE2), `font`, `align` left\|center\|right, `char_space` %, `line_space` %, `shadow` {`type` left_top\|right_top, `x`, `y`} |
| `group` | `items`: children with `x`, `y` inside the group, `kind` of this package or `rect`, `ellipse`, `line` |

## OLE object (`{"ole": {...}}`, a block) and 교정 부호 (run item)

`ole`: `src` (a file next to the spec: it is embedded as an OLE "Package", any size up to a few MB), `w`, `h` (default 26.72 x 21.96 mm), `inline`, `pos`, `wrap`, `side`, `caption` as for an object. The reader saves the embedded file next to the spec and gives its name as `src`.
`proof`: `{"proof": "lineattach" | "attach" | "delete" | "clipping", "text": "marked text"}` inside the list of a paragraph (`text`, not `t`); `lineattach` has no text. Rules OB18-OB20.

Example:
```json
{"body": [
  {"p": "text with a floating shape", "shapes": [{"type": "rect", "x": 0, "y": 5, "w": 40, "h": 20, "fill": "#9DC3E6", "hrel": "column", "halign": "right", "caption": "box"}]},
  {"pic": {"src": "a.png", "w": 30, "h": 20, "effect": "gray", "bright": 40, "crop": [0, 0, 50, 0], "border": "0.5mm solid #FF0000", "caption": "cropped"}},
  {"object": {"kind": "connector", "w": 40, "h": 20, "type": "elbow", "arrow": "both"}},
  {"object": {"kind": "textart", "w": 60, "h": 15, "text": "글맵시", "shape": "WAVE1"}}
]}
```
