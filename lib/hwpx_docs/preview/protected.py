"""Placeholder page for a protected HWPX (password or distribution document): it cannot be drawn without Hangul."""
import html

from ..core import protect

W, H = 210.0, 297.0
LINES = ('보호된 문서입니다', '암호가 걸렸거나 배포용으로 저장된 문서라서 내용을 그릴 수 없습니다.',
         '한글에서 열어 보호하지 않은 사본으로 저장한 뒤 다시 시도하십시오.')


def placeholder_pages(path):
    """[(width mm, height mm, svg text)] with one placeholder page if `path` is protected, else []."""
    info = protect.detect(path)
    if not info:
        return []
    rows = [(LINES[0], 8, 'bold', 110.0)] + [(t, 4, 'normal', 130.0 + 9 * i) for i, t in enumerate(LINES[1:])]
    text = ''.join('<text x="%s" y="%s" font-size="%s" font-weight="%s" text-anchor="middle" fill="#444" '
                   'font-family="&#x27;Malgun Gothic&#x27;,sans-serif">%s</text>' % (W / 2, y, sz, wt, html.escape(t))
                   for t, sz, wt, y in rows)
    frame = '<rect x="20" y="90" width="170" height="70" fill="#f4f4f4" stroke="#999" stroke-width="0.3"/>'
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %s %s" width="%smm" height="%smm" '
           'style="background:#fff;white-space:pre;display:block">\n<rect width="%s" height="%s" fill="#fff"/>\n%s\n%s\n'
           '</svg>' % (W, H, W, H, W, H, frame, text))
    return [(W, H, svg)]
