"""The user's fixed settings file that switches the layer on for every `hd` call (read by the core: lib/hwpx_docs/core/addons.py).

  %LOCALAPPDATA%\\hwpx-docs\\addons.json   {"addons": ["<add-on folder>"], "enforce": true}

`enforce: true` makes the core stop (`PRIVACY ADDON NOT LOADED`) when the add-on cannot be loaded, so a missing hook, a direct
`python lib/hd.py` call or an uninstalled add-on never shows a document's text. The SessionStart hook writes it; `pv.py enable|disable` (a
terminal) writes it too. The environment variable HWPX_DOCS_ADDONS only adds folders (a test override).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAME = 'hwpx-docs-privacy'


def path():
    p = os.environ.get('HWPX_DOCS_ADDONS_CONFIG')
    if p:
        return p
    base = os.environ.get('LOCALAPPDATA') if os.name == 'nt' else os.path.join(os.path.expanduser('~'), '.config')
    return os.path.join(base or os.path.expanduser('~'), 'hwpx-docs', 'addons.json')


def _load():
    p = path()
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return {'addons': [], 'enforce': False}


def _is_me(folder):
    try:
        return json.load(open(os.path.join(folder, 'hwpx-addon.json'), encoding='utf-8')).get('name') == NAME
    except (OSError, ValueError):
        return folder.rstrip('/\\').endswith(NAME)


def enable(enforce=True, user=False):
    """Put this add-on's folder into the settings file (an older folder of the same add-on is replaced); every other key (mode ...) is kept.
    The SessionStart hook does not switch the layer on again after the user switched it off (`pv.py disable`); `pv.py enable` (user=True) does.
    Returns the file path."""
    c = _load()
    if c.get('disabled_by_user') and not user:
        return path()
    folders = [f for f in c.get('addons', []) if not _is_me(f)]
    folders.append(ROOT.replace('\\', '/'))
    new = {**{k: v for k, v in c.items() if k != 'disabled_by_user'}, 'addons': folders, 'enforce': bool(enforce) or bool(c.get('enforce'))}
    if new != c:
        os.makedirs(os.path.dirname(path()), exist_ok=True)
        with open(path(), 'w', encoding='utf-8') as f:
            json.dump(new, f, ensure_ascii=False, indent=1)
    return path()


def disable():
    c = _load()
    c['addons'] = [f for f in c.get('addons', []) if not _is_me(f)]
    c['enforce'] = bool(c['addons']) and c.get('enforce', False)
    c['disabled_by_user'] = True
    os.makedirs(os.path.dirname(path()), exist_ok=True)
    with open(path(), 'w', encoding='utf-8') as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    return path()


def mode():
    """`standard` or `strict`, from the fixed settings file (key "mode"). The environment variable HWPX_PRIVACY_MODE can only raise it to strict;
    there is no `off`: the layer is switched off with `pv.py disable` (or by deleting the file), not by a variable a command could set."""
    return 'strict' if _load().get('mode') == 'strict' or os.environ.get('HWPX_PRIVACY_MODE', '').lower() == 'strict' else 'standard'


def disabled_by_user():
    """True after `pv.py disable`: the user switched the layer off, so the hooks neither refuse nor switch it on again."""
    return bool(_load().get('disabled_by_user'))


def is_enabled():
    """True when the fixed settings file lists this add-on."""
    return any(_is_me(f) for f in _load().get('addons', []))
