"""Preview drawers of the table package: gradient and picture cell fills, caption, floating table, wave lines (code: table/draw.py)."""
import functools

from ...table import draw
from .. import flow, svg
from . import register_paint, register_table_wrap

register_paint('gradient', draw.paint_gradient)
register_paint('image', draw.paint_image)
register_table_wrap(functools.partial(draw.wrap, geometry=flow.geometry))      # the page geometry places aligned tables
svg.EXTRA_STROKES.update({'wave': draw.stroke_wave, 'doublewave': draw.stroke_doublewave,      # line types, rules TB01
                          'thick3d': draw.stroke_none, 'thickrev3d': draw.stroke_none, '3d': draw.stroke_none, 'rev3d': draw.stroke_none})
