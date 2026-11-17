"""Preview drawers of the objects2 package: picture effects (brightness, contrast, gray, black and white, crop, border), captions,
aligned floating objects, and 교정 부호 as styled text (code: objects2/pdraw.py, objects2/proof.py; the object kinds register
themselves through DRAWS)."""
from ...objects2 import pdraw, proof
from . import register, register_prepare

register('picfx', pdraw.picfx)
register('proofmark', proof.mark)
register_prepare(pdraw.prepare)
register_prepare(proof.prepare)
