---
name: hwpx-objects
description: Drawing objects in HWPX — rectangles, ellipses, lines and arrows, text boxes, pictures, native Hangul charts (bar, line, pie, combined) and charts drawn with shapes. Use for 한글 도형, 글상자, 그림 넣기, 그래프/차트가 있는 문서.
---

# HWPX objects

`hd` = `python "${skillRoot}/lib/hd.py"`. Spec: `${skillRoot}/docs/spec.md` sections "Shape",
"Chart" and the `pic` block; rules S25, G01-G02 in `${skillRoot}/docs/rules.md`; status in
`${skillRoot}/docs/coverage.md` C6.

- Shapes: a block `{"shapes": [...], "p": "optional text"}` anchors floating objects to that paragraph.
  `x`, `y` are mm from the paper (or `rel: page|para`) top-left corner. Types: `rect` (with `text` = text box,
  `round`, `fill`, `line`), `ellipse`, `line` (`x2`, `y2`, `arrow`). Use shapes for anything that is not text or a
  table grid: free boxes, rules, circles, stamps, check marks.
- Pictures: `{"pic": {"src": "a.png", "w": 40, "h": 30, "inline": true}}`, path relative to the spec file; PNG, JPEG,
  GIF or BMP; the file is embedded (BinData).
- Charts: `{"chart": {"native": true, "type": "bar|hbar|line|pie|combo", "w": 140, "h": 80, "categories": [...],
  "series": [{"name": ..., "values": [...], "color": "#4472C4"}], "title": ..., "x_title": ..., "y_title": ...,
  "legend": "right|bottom|false", "labels": true}}` makes a real Hangul chart object: the user edits the data
  ("차트 데이터 편집"), type and style in Hangul (rules 5b CH01-CH11). Without `"native": true` the builder draws the chart
  with shapes (`bar` or `line` only; grid, axes, labels, legend): vector and editable, but not a chart object; it is also
  the automatic fallback (`FALLBACK chart: <reason>`). Example (shapes): `${skillRoot}/examples/chart-report/`.
- Equations are runs (`{"equation": "a over b"}`, skill hwpx-text).
- More chart kinds: `type: "area"` (`stacked`), `type: "scatter"` (`categories` = x numbers, `lines`, `x_min`, `x_max`), a
  second value axis with `axis: "secondary"` on a series (`y2_title`, `y2_min`, `y2_max`); keys in
  `${skillRoot}/lib/hwpx_docs/chart/spec.md`.
- More object keys (`docs/spec.md` "More keys of the feature packages" > "Objects"; rules OB01- in
  `${skillRoot}/lib/hwpx_docs/objects2/rules.md`): picture `bright`, `contrast`, `effect`, `crop`, `border`;
  `caption` on pictures, shapes, objects; position `hrel`, `halign`, `vpos`, `flow`, `overlap`, wrap side `side`,
  `same_para`; block `object` with `kind` `polygon`, `curve` (펜), `connector`, `textart` (글맵시), `group`; block `ole`
  (embedded file); run item `proof` (교정 부호).

Check: `hd build`, then render (skill hwpx-core) — floating objects can only be checked on the page image.
