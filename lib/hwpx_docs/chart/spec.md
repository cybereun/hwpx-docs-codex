# Native chart spec (`"native": true` in a `chart` block)

```json
{"chart": {"native": true, "type": "bar|hbar|line|pie|combo", "w": 140, "h": 80,
           "title": "분기별 실적", "x_title": "분기", "y_title": "백만 원", "legend": "right|left|top|bottom|false",
           "categories": ["1분기", "2분기"],
           "series": [{"name": "매출", "values": [120, 150], "color": "#C00000"},
                      {"name": "비용", "values": [80, 100], "type": "line"}],
           "labels": true, "stacked": false, "markers": true, "gridlines": true, "min": 0, "max": 200,
           "font": "함초롬돋움", "size": 10,
           "inline": true}}
```
A real Hangul chart object (`hp:chart` + `Chart/chart1.xml`, rules.md in this folder): the user edits data, type and style
in Hangul ("차트 데이터 편집"). `type`: `bar` = vertical columns, `hbar` = horizontal bars, `line`, `pie` (the first series
only; `series[0].colors` = slice colours; `"labels": "percent"` shows percentages), `combo` (each series has `type`
`bar` or `line`; the first series defaults to `bar`, the others to `line`). `title` `""` = Hangul's placeholder title
"차트 제목"; no `title` = none. `legend` defaults to shown for more than one series and for a pie. `unit` is shown as the
value-axis title. `inline` (default true) puts the chart in the text line; `"inline": false` with `pos` `{x, y, rel}`
and `wrap` floats it. `ooxml` holds a complete chart part as given (what `hd read` writes for a part with a kind that is
not modelled: area, scatter ..., or a part that says more than the spec, such as Hangul's default chart). With `ooxml`,
`hd read` also writes `view`: the data and main settings that a viewer draws (the preview); the builder ignores it and
writes `ooxml` as given. A chart that cannot be drawn natively (unknown `type`, a series with the wrong number
of values) prints `FALLBACK chart: <reason>` and is drawn with drawing objects (`bar` or `line`). The chart object has no
fallback for Hangul versions before OOXML chart support (not tested).

More kinds (rules CH12-CH14; Hangul render still to be checked): `type: "area"` (with `stacked`), `type: "scatter"` (`categories`
are the x values as numbers, shared by all series; `lines: true` joins the points; `x_min`, `x_max`, `x_title`), a combo
series with `type: "area"`, and `axis: "secondary"` on a series (any kind but pie): it goes to a second value axis on
the right (`y2_title`, `y2_min`, `y2_max`); at least one series stays on the primary axis.
