"""Fields and references package (coverage C7.03, C7.07-C7.10, C7.12). Depends on `hwpx_docs.core` only.

Public interface (one line): `forms.xml/parse/fill_file/listing` for form objects; run items `{"form": {...}}`,
`{"xref": ...}`, `{"index_mark": ...}`, `{"change": ...}` (track changes), blocks `{"toc": ...}`, `{"index": ...}` (spec keys in forms.py and refs.py); commands `hd form list|fill`. It registers itself (core/registry.py): COMMANDS, selftest,
BLOCKS 'run.form' (builder, run item), READS (reader), and the preview drawer module `preview/drawers/form.py`.

Files: forms.py (form objects: builder, reader, fill), refs.py (xref, index mark, generated 차례 and 색인), track.py (track changes), cli.py (`hd form`), tests.py (self-test), rules.md (F01..),
coverage.md (rows of this package). A fix to one of these items touches this folder only.
"""
COMMANDS = {
    'form': ('cli', [], 'list <in.hwpx> | fill <in.hwpx> <out.hwpx> --set name=value  form objects (check, radio, combo, edit)'),
}
BLOCKS = {'run.form': 'forms:piece', 'run.xref': 'refs:xref', 'run.index_mark': 'refs:index_mark',
          'toc': 'refs:toc', 'index': 'refs:index', 'run.change': 'track:change', 'doc.header': 'track:header'}
READS = {'checkBtn': 'forms:read', 'radioBtn': 'forms:read', 'btn': 'forms:read', 'comboBox': 'forms:read',
         'listBox': 'forms:read', 'edit': 'forms:read', 'scrollBar': 'forms:read'}


def selftest():
    from . import tests as t
    t.run()
