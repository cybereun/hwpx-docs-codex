"""Preview drawers of the table package: gradient and picture cell fills, caption, floating table, wave lines (code: table/draw.py)."""
from ...table import draw
from .. import flow, svg
from . import register_paint, register_table_wrap

register_paint('gradient', draw.paint_gradient)
register_paint('image', draw.paint_image)


def wrap(ctx, b, cst, w, layout_table, layout_para):
    """A table with pos that flows with the text is an ordinary table (layout.flow_table); every other one stays a floating object
    (table/draw.py)."""
    from ..layout import flow_table
    return draw.wrap(ctx, flow_table(b, w) or b, cst, w, layout_table, layout_para, geometry=flow.geometry)   # the page places aligned tables


register_table_wrap(wrap)
svg.EXTRA_STROKES.update({'wave': draw.stroke_wave, 'doublewave': draw.stroke_doublewave,      # line types, rules TB01
                          'thick3d': draw.stroke_none, 'thickrev3d': draw.stroke_none, '3d': draw.stroke_none, 'rev3d': draw.stroke_none})
