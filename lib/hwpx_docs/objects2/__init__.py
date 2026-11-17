"""Objects, second set (coverage C6.02, C6.08, C6.11-C6.14, C8.01-C8.04): picture effects, groups, 글맵시, wrap and anchors,
captions, connectors, free-form drawing, OLE (embedded file), 교정 부호. Depends on `hwpx_docs.core` only.

Public interface (one line): spec block `{"object": {...}}` (shapes.py: polygon, curve, connector, textart, group), `{"ole": {...}}`
(ole.py), run item `{"proof": kind, "t": text}` (proof.py); extra keys of the core pictures and shapes (pic.py: bright, contrast,
effect, crop, border; pos.py: pos extras, side, caption). It registers itself (core/registry.py): BLOCKS, READS, POST, EXTRAS, DRAWS,
selftest.

Files: pos.py (hp:pos, textFlow, caption), pic.py (picture extras; POST / EXTRAS of pic and shape), shapes.py (the object kinds),
ole.py (OLE package: compound file writer and reader), proof.py (교정 부호), draw.py + pdraw.py (viewer drawing; preview/drawers/
objects2.py registers pdraw and proof), corpus.py (Hangul sample maker, dev tool), tests.py (self-test), fixtures/ (Hangul-made
samples), rules.md (OB01-), spec.md, coverage.md. A fix to these objects touches this folder only (plus the small hooks in
core/registry.py, objects/objects.py, core/read.py, core/build.py).
"""
_OBJECT_TAGS = ('polygon', 'curve', 'connectLine', 'textart', 'container')
BLOCKS = {'object': 'shapes:block', 'ole': 'ole:block', 'run.proof': 'proof:run'}      # builder: blocks and the run item `proof`
READS = dict({t: 'shapes:read' for t in _OBJECT_TAGS}, ole='ole:read')                 # reader: the object elements
POST = {'pic': 'pic:pic_post', 'shape': 'pic:shape_post'}   # builder: extra keys of pictures and rect / ellipse / line
EXTRAS = {'pic': 'pic:pic_extra', 'shape': 'pic:shape_extra'}   # reader: the same keys back
DRAWS = {'object': 'pdraw:svg_object', 'ole': 'pdraw:svg_ole'}      # viewer: the object kinds


def selftest():
    from . import tests as t
    t.run()
