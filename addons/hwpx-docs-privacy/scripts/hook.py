"""Hook entry of the privacy add-on: python hook.py <session-start|pre-tool|prompt>; the hook JSON arrives on stdin.

Output (Claude Code hook protocol): PreToolUse -> permissionDecision deny with a reason; UserPromptSubmit -> decision block;
Nothing is printed when the call is allowed.
A crash of this script must not leave a gap: any failure ends with exit code 2 (the call is blocked), also an unreadable input.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def say(obj):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))


def decide(event, decision, reason):
    """A refusal (deny) or a question (ask) for a tool call; a block for a prompt."""
    if event == 'prompt':
        say({'decision': 'block', 'reason': reason})
    else:
        say({'hookSpecificOutput': {'hookEventName': 'PreToolUse', 'permissionDecision': decision, 'permissionDecisionReason': 'privacy add-on: ' + reason}})


def main(event):
    sys.stdin.reconfigure(encoding='utf-8')
    raw = sys.stdin.read()
    if not raw.strip():
        raise ValueError('no hook input')
    data = json.loads(raw)
    if event == 'session-start':
        from hwpxpriv import settings, vault
        msg = None
        try:                                              # the fixed file: on for every hd call, also outside this session
            if settings.disabled_by_user():               # you switched it off (`pv.py disable`): it stays off until `pv.py enable`
                say({'systemMessage': 'The privacy layer is switched off (you ran `pv.py disable`). `hd` shows real values. Switch it on with `python scripts/pv.py enable` in a terminal.'})
                vault.audit('session-start', enabled=False, disabled_by_user=True)
                return
            settings.enable()
        except OSError as e:
            msg = (f'The privacy layer could not write its settings file ({settings.path()}: {type(e).__name__}). Tool calls on documents are refused '
                   'until it can: fix the folder or run `python scripts/pv.py enable` in a terminal.')
        env = os.environ.get('CLAUDE_ENV_FILE')
        if env:                                           # every Bash command of this session loads the add-on
            with open(env, 'a', encoding='utf-8') as f:
                f.write(f'export HWPX_DOCS_ADDONS="{ROOT.replace(chr(92), "/")}"\n')
        with open(os.path.join(vault.home(), 'session.json'), 'w') as f:
            json.dump({'session': data.get('session_id'), 'root': ROOT}, f)
        vault.audit('session-start', enabled=msg is None)
        if msg:
            say({'systemMessage': msg})
        return
    from hwpxpriv import gates, settings
    tool, ti = data.get('tool_name', ''), data.get('tool_input') or {}
    if settings.disabled_by_user():                           # switched off by you: no gate
        return
    if event == 'pre-tool' and not settings.is_enabled():     # the fixed file is missing: nothing is protected, so nothing is let through
        decide(event, 'deny', f'the privacy layer is not switched on (settings file {settings.path()} is missing). Run `python scripts/pv.py enable` in a terminal.')
        return
    g = gates.Gate()
    if event == 'pre-tool':
        res = None
        if tool == 'Read':
            res = g.pre_read(ti.get('file_path', ''))
        elif tool in ('Bash', 'PowerShell', 'Monitor'):
            res = g.pre_bash(ti.get('command', ''), data.get('cwd') or '.')
        elif tool == 'Grep':
            res = g.pre_grep(ti)
        if res:
            decide(event, *res)
    elif event == 'prompt':
        reason = g.prompt(data.get('prompt', ''))
        if reason:
            decide(event, 'deny', reason)


if __name__ == '__main__':
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else '')
    except BaseException as e:                              # any failure ends with exit code 2: the call is not let through
        sys.stderr.write(f'privacy add-on: the check failed ({type(e).__name__}); nothing was read or sent. Run `python scripts/pv.py status`.\n')
        sys.exit(2)
