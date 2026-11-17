"""Runs: text, links, fields, notes, equations, bookmarks."""
from ..core import registry
from ..core.units import CHAR_KEYS, color, esc, hu


class TextMixin:
    """Runs: text, links, fields, notes, equations, bookmarks. Mixed into core.build.Doc."""

    # ---- runs and paragraphs ----
    def run_xml(self, piece, ctx):
        """One run item -> XML of one hp:run (or several)."""
        if isinstance(piece, str):
            piece = {'t': piece}
        piece = self.klass(piece)
        c = dict(ctx)
        c.update({k: v for k, v in piece.items() if k in CHAR_KEYS})
        cid = self.head.char_pr(c)
        if 'link' in piece:      # hyperlink field around the text (corpus/gongmun: Hangul made it)
            fid = 1300000000 + self.next_obj()
            url = str(piece['link'])
            base = self.head.char_pr(ctx)
            text = esc(piece.get('t', url))
            return (f'<hp:run charPrIDRef="{base}"><hp:ctrl><hp:fieldBegin id="{fid}" type="HYPERLINK" name="" editable="0" '
                    f'dirty="1" zorder="-1" fieldid="627600491"><hp:parameters cnt="6" name="">'
                    '<hp:integerParam name="Prop">0</hp:integerParam>'
                    f'<hp:stringParam name="Command">{esc(url.replace(":", chr(92) + ":"))};1;0;0;</hp:stringParam>'
                    f'<hp:stringParam name="Path">{esc(url)}</hp:stringParam>'
                    '<hp:stringParam name="Category">HWPHYPERLINK_TYPE_URL</hp:stringParam>'
                    '<hp:stringParam name="TargetType">HWPHYPERLINK_TARGET_BOOKMARK</hp:stringParam>'
                    '<hp:stringParam name="DocOpenType">HWPHYPERLINK_JUMP_CURRENTTAB</hp:stringParam>'
                    '</hp:parameters></hp:fieldBegin></hp:ctrl></hp:run>'
                    f'<hp:run charPrIDRef="{cid}"><hp:t>{text}</hp:t></hp:run>'
                    f'<hp:run charPrIDRef="{base}"><hp:ctrl><hp:fieldEnd beginIDRef="{fid}" fieldid="627600491"/></hp:ctrl>'
                    '<hp:t/></hp:run>')
        if 't' in piece and 'field' not in piece:
            parts = str(piece['t']).split('\t')
            body = '<hp:tab width="0" leader="0" type="0"/>'.join(esc(p) for p in parts)
            if c.get('highlight'):          # 형광펜 (corpus/diff/char_markpen)
                body = f'<hp:markpenBegin color="{color(c["highlight"])}"/>{body}<hp:markpenEnd/>'
            return f'<hp:run charPrIDRef="{cid}"><hp:t>{body}</hp:t></hp:run>'
        if piece.get('tab'):
            return f'<hp:run charPrIDRef="{cid}"><hp:t><hp:tab width="0" leader="0" type="0"/></hp:t></hp:run>'
        if 'equation' in piece:          # Hangul equation script, e.g. "a over b" (corpus/diff/equation_add)
            e = piece['equation'] if isinstance(piece['equation'], dict) else {'script': piece['equation']}
            oid = self.next_obj()
            return (f'<hp:run charPrIDRef="{cid}"><hp:equation id="{1400000000 + oid}" zOrder="{oid}" numberingType="EQUATION" '
                    'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" dropcapstyle="None" version="Equation Version 60" '
                    f'baseLine="{e.get("baseline", 66)}" textColor="{color(e.get("color"))}" baseUnit="{hu(e.get("size", c.get("size", 10)), "pt")}" '
                    f'lineMode="CHAR" font="{esc(e.get("font", "HancomEQN"))}">'
                    f'<hp:sz width="{hu(e.get("w", 1))}" widthRelTo="ABSOLUTE" height="{hu(e.get("h", 1))}" heightRelTo="ABSOLUTE" protect="0"/>'
                    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" allowOverlap="0" holdAnchorAndSO="0" '
                    'vertRelTo="PARA" horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
                    '<hp:outMargin left="56" right="56" top="0" bottom="0"/><hp:shapeComment>수식입니다.</hp:shapeComment>'
                    f'<hp:script>{esc(e["script"])}</hp:script></hp:equation><hp:t/></hp:run>')
        if 'bookmark' in piece:
            return f'<hp:run charPrIDRef="{cid}"><hp:ctrl><hp:bookmark name="{esc(piece["bookmark"])}"/></hp:ctrl><hp:t/></hp:run>'
        if 'field' in piece:             # 누름틀 (click-here field): {'field': name, 't': guide text, 'memo': help}
            fid = 1300000000 + self.next_obj()
            guide, memo = str(piece.get('t', '')), str(piece.get('memo', ''))
            # Command = "Clickhere:set:<length of body>:<body> " (corpus/diff/field_add: 53 for this body)
            body = f'Direction:wstring:{len(guide)}:{guide} HelpState:wstring:{len(memo)}:{memo} '
            cmd = f'Clickhere:set:{len(body)}:{body} '
            base = self.head.char_pr(ctx)
            return (f'<hp:run charPrIDRef="{base}"><hp:ctrl><hp:fieldBegin id="{fid}" type="CLICK_HERE" name="{esc(piece["field"])}" '
                    'editable="1" dirty="0" zorder="-1" fieldid="627272811"><hp:parameters cnt="4" name="">'
                    '<hp:integerParam name="Prop">9</hp:integerParam>'
                    f'<hp:stringParam name="Command" xml:space="preserve">{esc(cmd)}</hp:stringParam>'
                    f'<hp:stringParam name="Direction">{esc(guide)}</hp:stringParam>'
                    f'<hp:stringParam name="HelpState">{esc(memo)}</hp:stringParam></hp:parameters></hp:fieldBegin></hp:ctrl></hp:run>'
                    f'<hp:run charPrIDRef="{cid}"><hp:t>{esc(guide)}</hp:t></hp:run>'
                    f'<hp:run charPrIDRef="{base}"><hp:ctrl><hp:fieldEnd beginIDRef="{fid}" fieldid="627272811"/></hp:ctrl><hp:t/></hp:run>')
        if 'endnote' in piece:
            return f'<hp:run charPrIDRef="{cid}">{self.footnote(piece["endnote"], c, kind="endNote")}<hp:t/></hp:run>'
        if 'new_page_num' in piece:      # 새 번호로 시작 (corpus/diff/page_num_start)
            return (f'<hp:run charPrIDRef="{cid}"><hp:ctrl><hp:newNum num="{int(piece["new_page_num"])}" numType="PAGE"/>'
                    '</hp:ctrl><hp:t/></hp:run>')
        if 'xml' in piece:               # raw OWPML run content, written as given (no id remapping)
            return f'<hp:run charPrIDRef="{cid}">{piece["xml"]}</hp:run>'
        if 'footnote' in piece:
            return f'<hp:run charPrIDRef="{cid}">{self.footnote(piece["footnote"], c)}<hp:t/></hp:run>'
        if piece.get('page_num'):
            fmt = piece.get('format', 'DIGIT').upper()
            return (f'<hp:run charPrIDRef="{cid}"><hp:ctrl><hp:autoNum num="1" numType="PAGE"><hp:autoNumFormat '
                    f'type="{fmt}" userChar="" prefixChar="" suffixChar="" supscript="0"/></hp:autoNum></hp:ctrl></hp:run>')
        if 'pic' in piece:
            return f'<hp:run charPrIDRef="{cid}">{self.pic(piece["pic"], inline=True)}<hp:t/></hp:run>'
        if 'table' in piece:
            return f'<hp:run charPrIDRef="{cid}">{self.table(piece["table"], c, inline=True)}<hp:t/></hp:run>'
        for key in piece:               # a feature package's run item (registry.py BLOCKS key 'run.<key>')
            for handler in registry.block_handlers('run.' + key):
                r = handler(self, piece, c)
                if r is not None:
                    return r
        raise ValueError(f'unknown run item: {piece!r}')

    def footnote(self, content, ctx, kind='footNote'):
        """Footnote (kind 'footNote') or endnote ('endNote', corpus/diff/endnote_add): same structure."""
        counter = 'notes' if kind == 'footNote' else 'endnotes'
        setattr(self, counter, getattr(self, counter, 0) + 1)
        n = getattr(self, counter)
        blocks = [{'p': content}] if isinstance(content, str) else content
        c = dict(ctx)
        c.update(self.spec.get('footnote_style', {'size': 9}))
        auto = (f'<hp:ctrl><hp:autoNum num="{n}" numType="{kind.upper()}"><hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" '
                f'suffixChar=")" supscript="0"/></hp:autoNum></hp:ctrl>')
        first = dict(blocks[0]) if isinstance(blocks[0], dict) else {'p': blocks[0]}
        text = first.get('p', '')
        runs = [' ' + text] if isinstance(text, str) else [' '] + list(text)
        # the number run takes the char shape of the note text (FIRST is replaced in para_xml)
        p0 = self.para_xml(runs, c, {k: v for k, v in first.items() if k != 'p'}, f'<hp:run charPrIDRef="FIRST">{auto}</hp:run>')
        rest = ''.join(self.blocks_xml(blocks[1:], c)) if len(blocks) > 1 else ''
        base = 2000000000 if kind == 'footNote' else 2100000000
        return (f'<hp:ctrl><hp:{kind} number="{n}" suffixChar="41" instId="{base + n}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="TOP" linkListIDRef="0" '
                f'linkListNextIDRef="0" textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">{p0}{rest}</hp:subList>'
                f'</hp:{kind}></hp:ctrl>')
