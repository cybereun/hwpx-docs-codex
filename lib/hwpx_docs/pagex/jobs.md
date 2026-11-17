# pagex: Hangul jobs

Done 2026-11-14 (agreed Hangul window): `hd pagex run` (54 files: baselines and variants in `fixtures/`), `hd roundtrip` of 40
files (ink difference 0.00), probes for `BreakColDef`, `LabelTemplate`, `MasterPageFront`, `CharGrid`.

Done in the second window (page2): `hd roundtrip` of cols_mid_S and wonggoji_grid_S (0.00); pairs pg_cols, pg_label, master_front, wonggoji_grid made again; 7 vertical writing renders (`vt_*`, for the renderer owner).

Still open (old list, partly done):
- `hd roundtrip` of `fixtures/cols_mid_S.hwpx` (a two-column change inside a page) and `fixtures/wonggoji_grid_S.hwpx`.
- Make the pairs of the groups `pg_cols` (baseline + `cols_mid`, `cols_sec`), `pg_label` and `master_front` again with
  `hd pagex run pg_cols pg_label master_front wonggoji_grid` (the batch of 2026-11-14 ran an older version of these groups; the
  `_S` files are single samples from the probes).
- Needs a user-made sample: 겹침 (`pageDuplicate="1"`): COM `MasterPageDuplicate` returns False.
- A two-page sample of line numbers with restart 0, 1, 2 (what each value restarts).
