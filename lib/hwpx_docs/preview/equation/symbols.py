"""Keyword tables of the Hangul equation script: symbols, functions, structure words. Names and glyphs follow the public
command list of the Hangul help pages and the equation file-format document (symbol tables); the code points are the
standard Unicode characters of those symbols. Look-up: `symbol(name)`, `FUNCTIONS`, `STRUCT`."""

# ---- Greek ---------------------------------------------------------------------------------------------------------
_LOW = 'alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega'.split()
_LOW_CH = 'αβγδεζηθικλμνξοπρστυφχψω'
GREEK = {n: c for n, c in zip(_LOW, _LOW_CH)}
GREEK.update({n.capitalize(): c.upper() for n, c in zip(_LOW, _LOW_CH)})
GREEK.update(vartheta='ϑ', varpi='ϖ', varsigma='ς', varupsilon='ϒ', varphi='ϕ', varepsilon='ϵ')

# name -> glyph. Case matters where Hangul has two symbols (larrow / LARROW).
SYMBOLS = dict(GREEK)
SYMBOLS.update({
    'ALEPH': 'ℵ', 'HBAR': 'ℏ', 'IMATH': 'ı', 'JMATH': 'ȷ', 'OHM': 'Ω', 'ELL': 'ℓ', 'LITER': 'ℓ', 'WP': '℘', 'IMAG': 'ℑ',
    'ANGSTROM': 'Å', 'MHO': '℧',
    'COPROD': '∐', 'CAP': '∩', 'SQCAP': '⊓', 'SQCUP': '⊔', 'OPLUS': '⊕', 'OMINUS': '⊖', 'OTIMES': '⊗', 'ODOT': '⊙',
    'OSLASH': '⊘', 'VEE': '∨', 'WEDGE': '∧', 'SUBSET': '⊂', 'SUPSET': '⊃', 'SUBSETEQ': '⊆', 'SUPSETEQ': '⊇', 'IN': '∈',
    'OWNS': '∋', 'notin': '∉', 'LEQ': '≤', 'LE': '≤', 'GEQ': '≥', 'GE': '≥', 'SQSUBSET': '⊏', 'SQSUPSET': '⊐',
    'SQSUBSETEQ': '⊑', 'SQSUPSETEQ': '⊒', '<<': '≪', '>>': '≫', 'LLL': '⋘', '>>>': '⋙', '<<<': '⋘', 'PREC': '≺', 'SUCC': '≻',
    'UPLUS': '⊎', 'SMALLUNION': '∪', 'SMALLINTER': '∩', 'SMALLPROD': '∏', 'SMALLSUM': '∑',
    'PLUSMINUS': '±', 'MINUSPLUS': '∓', 'times': '×', 'TIMES': '×', 'DIV': '÷', 'DIVIDE': '÷', 'CIRC': '∘', 'BULLET': '•',
    'DEG': '°', 'AST': '∗', 'STAR': '★', 'BIGCIRC': '○', 'EMPTYSET': '∅', 'THEREFORE': '∴', 'BECAUSE': '∵',
    'IDENTICAL': '∷', 'EXIST': '∃', 'neq': '≠', 'ne': '≠', 'NE': '≠', 'NEQ': '≠', '!=': '≠', 'DOTEQ': '≐', 'image': '≒', 'REIMAGE': '≓',
    'SIM': '∼', 'APPROX': '≈', 'SIMEQ': '≃', 'CONG': '≅', '==': '≡', 'EQUIV': '≡', 'ASYMP': '≍', 'ISO': '≂',
    'DIAMOND': '◇', 'DSUM': '∔', 'FORALL': '∀', 'prime': '′', 'PARTIAL': '∂', 'inf': '∞', 'INF': '∞', 'LNOT': '¬',
    'PROPTO': '∝', 'XOR': '⊻', 'TRIANGLED': '▽', 'DAGGER': '†', 'DDAGGER': '‡',
    'larrow': '←', 'rarrow': '→', 'uparrow': '↑', 'downarrow': '↓', 'LARROW': '⇐', 'RARROW': '⇒', 'UPARROW': '⇑',
    'DOWNARROW': '⇓', 'udarrow': '↕', 'lrarrow': '↔', 'UDARROW': '⇕', 'LRARROW': '⇔', 'nwarrow': '↖', 'searrow': '↘',
    'nearrow': '↗', 'swarrow': '↙', 'hookleft': '↩', 'hookright': '↪', 'mapsto': '↦', 'vert': '|', 'VERT': '‖',
    '<-': '←', '->': '→', '<->': '↔', '<=': '≤', '>=': '≥',
    'cdots': '⋯', 'CDOTS': '⋯', 'LDOTS': '…', 'ldots': '…', 'VDOTS': '⋮', 'DDOTS': '⋱', 'TRIANGLE': '△', 'ANGLE': '∠',
    'MSANGLE': '∡', 'SANGLE': '∢', 'RTANGLE': '⊾', 'VDASH': '⊢', 'HLEFT': '⊣', 'BOT': '⊥', 'TOP': '⊤', 'MODELS': '⊨',
    'LAPLACE': 'ℒ', 'CENTIGRADE': '℃', 'FAHRENHEIT': '℉', 'LSLANT': '╱', 'RSLANT': '╲', 'att': '※', 'hund': '‰',
    'thou': '‱', 'well': '#', 'base': '⌂', 'benzene': '⌬', 'lbrace': '{', 'rbrace': '}', 'langle': '⟨', 'rangle': '⟩',
    'lceil': '⌈', 'rceil': '⌉', 'lfloor': '⌊', 'rfloor': '⌋',
})
# Characters that sit between operands with room around them (the Hangul equation font gives them a 1 em advance)
RELATIONS = set('=<>≤≥≠≡≈≃≅≪≫⋘⋙≺≻⊂⊃⊆⊇⊏⊐⊑⊒∈∋∉∝∼≐≒≓≍≂←→↔⇐⇒⇔↑↓↕⇑⇓⇕↖↘↗↙↩↪↦⊢⊣⊥⊤⊨∴∵∷')
BINARY = set('+−±∓×÷∘•∗★○∪∩⊓⊔⊕⊖⊗⊙⊘∨∧⊎∔⊻')

# Words that are always upright (basic functions and reserved words)
FUNCTIONS = set('sin cos tan cot sec cosec csc sinh cosh tanh coth arcsin arccos arctan arc asin acos atan log ln lg exp Exp '
                'max min gcd lcm mod det if for and hom ker deg arg dim Pr or lim Lim'.split())

# Big operators: glyph, limits above and below (True) or at the side (False)
BIGOPS = {'sum': ('∑', True), 'prod': ('∏', True), 'coprod': ('∐', True), 'union': ('⋃', True), 'inter': ('⋂', True),
          'int': ('∫', False), 'oint': ('∮', False), 'dint': ('∬', False), 'tint': ('∭', False), 'odint': ('∯', False),
          'otint': ('∰', False)}

# Structure words (lower case). Prefix with operands, infix, state changes.
STRUCT = set('over atop choose binom sqrt root of from to left right matrix pmatrix bmatrix dmatrix cases pile lpile rpile '
             'eqalign hat check tilde acute grave dot ddot bar vec dyad under arch not bigg rm it bold rmbold scale color '
             'sub sup lsub lsup rel buildrel ladder sladder longdiv col lcol rcol phantom'.split())
ACCENTS = {'hat', 'check', 'tilde', 'acute', 'grave', 'dot', 'ddot', 'bar', 'vec', 'dyad', 'under', 'arch'}
UNSUPPORTED = set()          # every command of the Hangul help is drawn

# bracket characters usable after left / right
BRACKETS = {'(': '(', ')': ')', '[': '[', ']': ']', '|': '|', '‖': '‖', 'lbrace': '{', 'rbrace': '}', 'langle': '⟨',
            'rangle': '⟩', 'lceil': '⌈', 'rceil': '⌉', 'lfloor': '⌊', 'rfloor': '⌋', 'vert': '|', 'VERT': '‖', '<': '⟨', '>': '⟩'}


def symbol(name):
    """Glyph of a symbol keyword, or None. Exact name first, then the lower-case name, then upper-case."""
    if name in SYMBOLS:
        return SYMBOLS[name]
    if name.isupper() and len(name) > 1 and name.capitalize() in GREEK:       # ALPHA = Alpha
        return GREEK[name.capitalize()]
    low = name.lower()
    if low in SYMBOLS and not name.isupper():
        return SYMBOLS[low]
    if name.upper() in SYMBOLS:
        return SYMBOLS[name.upper()]
    if name.isupper() and low in SYMBOLS:
        return SYMBOLS[low]
    return None
