# Rules of the fields package (F01-)

Status words: **sample** = Hangul wrote it or saved it again (fixtures in `fixtures/`, round trip ink 0.00); **model** =
from Hancom's open OWPML model (`hancom-io/hwpx-owpml-model`, names only, `docs/owpml-crosscheck.md`); **own** = this
package's choice. Made 2026-11-14 in one Hangul window (hidden, security module, Quit after).

## Form objects (C7.10)

How the samples were made: `FormObjCreator*` actions wait for a mouse drag (no object by COM). The builder wrote the
XML by the model's names, Hangul opened it and drew it (check mark, radio dot, combo arrow, edit text, button, scroll
bar) and saved it again; that file is `fixtures/form_objects.hwpx`. The builder's element text equals Hangul's saved
text except the char shape number (`formCharPr charPrIDRef`: Hangul renumbers) and the three items below.

| id | rule | status |
|---|---|---|
| F01 | A form object is a child of `hp:run`, followed by `<hp:t/>`: `hp:checkBtn`, `hp:radioBtn`, `hp:btn` (push button), `hp:comboBox`, `hp:listBox`, `hp:edit`, `hp:scrollBar`. | sample |
| F02 | Hangul's order: the attributes of the type, then `name foreColor backColor groupName tabStop editable tabOrder enabled borderTypeIDRef drawFrame printable command`; children `formCharPr` (not for a scroll bar), `listItem` or `text`, `sz`, `pos` (treatAsChar=1 in a text line), `outMargin`. It writes no shape attributes (`id zOrder ...`) and reads them when given. | sample |
| F03 | `checkBtn` / `radioBtn`: `caption value radioGroupName triState backStyle`; `value` = `UNCHECKED` `CHECKED` `INDETERMINATE`; the radio buttons of one group share `radioGroupName`. `btn`: `caption radioGroupName triState`. Default `backColor` `#F0F0F0` (buttons, scroll bar), `#FFFFFF` (edit, combo, list). | sample |
| F04 | `comboBox`: `listBoxRows listBoxWidth editEnable selectedValue`; `listBox`: `itemHeight topIdx` (4294967295 = none) `selectedValue`; items are `hp:listItem displayText value`. | sample (items: see F08) |
| F05 | `edit`: `multiLine passwordChar maxLength` (2147483647 = no limit) `scrollBars tabKeyBehavior numOnly readOnly alignText`; the text is `<hp:text>`. | sample |
| F06 | `scrollBar`: `delay largeChange smallChange min max page value type`; the spec builds only the default range. | sample |
| F07 | A form object the spec cannot hold (floating, a child or attribute without a spec key) stays raw OWPML and is written back as read. The preview draws what it can read and a dashed box for the rest. | own |
| F08 | **Limits (Hangul side):** (a) of a combo or list box Hangul keeps only the `value` of the FIRST `listItem` when it opens this XML (`displayText` and the other items vanish, tried 10 variants); (b) in an edit box only the first line of the text stays (`&#10;`, CRLF and LF all lost); (c) `borderTypeIDRef="0"` prints no frame. The real form of several items and of a frame needs a Hangul-made sample (made by hand in Hangul). | sample |
| F09 | Fill (`hd form fill`): check, radio: true/false; a radio group is chosen by the group name and the caption of the button; combo and list take an item's text or value (any other value is refused); edit replaces `<hp:text>`. Nothing else in the file changes. | own |

## References (C7.03, C7.08, C7.07)

| id | rule | status |
|---|---|---|
| X01 | Cross-reference (상호 참조): COM `InsertCrossReference` with `HActionCrossRef.Command = <target>` writes a run with `fieldBegin type="CROSSREF" name="" editable="0" dirty="0" zorder="-1" fieldid="628650598"`, parameters `Fiexde`(sic)=1, `Prop`=0, `Command`=<target> (left out when empty), `RefPath`=<target with `:` as `\:`>`;`, `RefType`=`TARGET_TABLE`, `RefContentType`=`OBJECT_TYPE_PAGE`, `RefHyperLink`=false, `RefOpenType`=`HWPHYPERLINK_JUMP_CURRENTTAB`, then `fieldEnd`; nothing between begin and end (Hangul shows the number or page itself). Spec `{"xref": {"target", "ref_type", "content", "link"}}`. The reader keeps the field as raw OWPML. **Limit:** other `RefType` and `RefContentType` values (heading, figure, equation, bookmark; number or text instead of page) are not known: COM sets only `Command`. | sample (default type) |
| X02 | Index mark (색인 표시): `hp:ctrl/hp:indexmark` with `hp:firstKey` and optional `hp:secondKey`, put at the end of the selection. Spec run item `{"index_mark": {"first", "second"}}`. Not printed. | sample |
| X03 | Index (찾아보기 만들기) is static text: a group paragraph `(A)`, the first key as a paragraph, the second key as a paragraph with three leading spaces, a tab and the page number(s). The builder block `{"index": {...}}` writes the same kind of paragraphs (group, key, second key, dotted right tab, page numbers); the exact styles of Hangul's own index are not copied (paragraph look only). | sample (text), own (look) |
| X04 | Table of contents (차례): COM `MakeContents` raises a server exception in every call form tried (default values, `Make`, `Level`, `Position`, `Styles` array: `CreateItemArray` returns nothing). The builder block `{"toc": {"levels", "title", "pages"}}` writes static entries: heading text, dotted right tab at the text width, page number, indented per level. Headings are the blocks with `outline_level`. | own |
| X05 | `pages: "auto"` (toc, index): build once with masked entry text (same room), let the preview renderer (`registry.backend('pages', 'preview')`) tell the page of each heading or mark, build again. Without the renderer the page number is left out. | own |
| X06 | 누름틀 guide text: the guide text is drawn only when the caret (`settings.xml` `CaretPosition pos`) is NOT at the field. A Hangul-made file with its caret in the field prints nothing; the same file with the caret at 0, and the builder's file, print the red italic guide. The builder is right; compare rendered pages of both files with the same caret (ink 0.00 then). | sample (C7.09) |
| X07 | Track changes cannot be switched on by COM (`TrackChangeApply` no-op, `hwp.IsTrackChange` read only, no action name, Ctrl+Shift+G no effect), so the sample is made by hand (`fixtures/track_change.hwpx`); rules T01-T05. | sample |

## Track changes (C7.12), from `fixtures/track_change.hwpx` (made by hand in Hangul: 변경 내용 추적 on, one insertion, one deletion, one bold change)

| id | rule | status |
|---|---|---|
| T01 | Header: `hh:trackChanges itemCnt` (child of `hh:refList`, after `hh:styles`) holds one `hh:trackChange type="Insert|Delete|CharShape" date authorID hide="0" id` per change (`charshapeID` = the char shape before the change, for CharShape); `hh:trackChangeAuthors` holds `hh:trackChangeAuthor name mark="1" id`. The ids are made in the order the user typed, not in document order. | sample |
| T02 | Body: inserted or deleted text stays in the run, inside `hp:t`: `<hp:insertBegin Id="n" TcId="n"/>text<hp:insertEnd Id="n" TcId="n" paraend="0"/>` (`deleteBegin/deleteEnd` the same; `paraend="1"` when the change includes the paragraph end). A format change is a run with the new `charPrIDRef` and `charTcId="n"`. | sample (paraend=1: from the model name only) |
| T03 | Hangul draws inserted text in red with an underline, deleted text in red with a strike line, a format change in its new look, and a red change bar in the left margin of the lines with changes. | sample (render) |
| T04 | Tracking is on when the flags of `hh:trackchageConfig` (sic, at the end of `hh:head`) are 57; the template has 56 (off). The builder sets 57 when the spec has a change. | sample |
| T05 | Spec run item `{"change": {"type": "insert|delete|format", "t", "author", "date", "id", "paraend"}}`, char keys at item level (for `format` the new look). Defaults: author `hwpx-docs`, date `2000-01-01T00:00:00Z`. **Limits:** a format change records the char shape of the paragraph (without the item's keys) as the old look; accepting or rejecting changes is not built; the preview draws each piece as one object (no wrap inside a long piece) and no change bar. | own |
