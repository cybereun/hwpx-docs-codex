"""Hangul (Hancom Office) COM session for corpus making, rendering and open checks.

Rules this module keeps:
- It starts a NEW hidden Hangul process (DispatchEx). It never attaches to a running Hangul
  (no GetActiveObject), so the user's open documents are not touched.
- It never ships, downloads, installs or registers a DLL, and never answers Hangul's file-access prompt
  ("한글을 이용하여 위 파일에 접근하려는 시도 ..."). That prompt comes when Hangul OPENS an existing file; only
  the user answers it ("모두 허용" = allow for this Hangul session). While it is open during Open(), the
  watchdog waits up to `prompt_wait` seconds; with no answer it closes it (= deny) and the batch stops.
  Use one Hwp session for a batch of files, so the user answers once per batch.
- Opt-in, OFF by default: if the USER installed Hancom's official automation security module and set
  the environment variable HWPX_DOCS_SECURITY_MODULE (old name HWPX_DOCS_MODULE) to its registry value name
  (HKCU\\Software\\HNC\\HwpAutomation\\Modules; read only, never written), each session calls
  RegisterModule("FilePathCheckDLL", <that name>) right after DispatchEx, before any Open, and logs one line
  "security module: on" or "security module: off (...)". Then the prompt does not come: the user's own setup removes
  it (docs/rules.md C02); scripts still never click or answer the prompt.
- The Hangul window stays hidden and is never activated: the watchdog (every 0.2 s) hides our main window again with
  ShowWindow(SW_HIDE) when Hangul shows it, and hides any other popup at once (an image of it is saved first); a popup
  that still exists after 8 s is closed (a short progress window is hidden, not closed, so the save goes on). The
  file-access prompt during Open() is left visible for the user. It never calls SetForegroundWindow.
- A watchdog kills ONLY the process that this session started, if a call blocks longer than
  `timeout` seconds (for example a hidden dialog). Then the next COM call raises an error.
- On exit it calls Quit, then kills its own process if it is still alive.

Needs pywin32. Use:  with Hwp() as h: h.new(); h.text('...'); h.save('a.hwpx')
"""
from ..core import tmpdir
import os
import subprocess
import tempfile
import threading
import time


SECURITY_KEY = r'Software\HNC\HwpAutomation\Modules'


def security_module(hwp):
    """Opt-in official security module (README "접근 허용 창 없애기"): True when it is registered for this session."""
    name = os.environ.get('HWPX_DOCS_SECURITY_MODULE') or os.environ.get('HWPX_DOCS_MODULE')
    if not name:
        print('security module: off', flush=True)
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SECURITY_KEY) as k:
            winreg.QueryValueEx(k, name)                    # read only: the user made the value
    except OSError:
        print(f'security module: off (no value "{name}" under HKCU\\{SECURITY_KEY})', flush=True)
        return False
    ok = bool(hwp.RegisterModule('FilePathCheckDLL', name))
    print('security module: on' if ok else f'security module: off (RegisterModule("{name}") failed)', flush=True)
    return ok


def _hide(hwnd):
    """Hide a window without activating anything (never SetForegroundWindow)."""
    try:
        import win32con
        import win32gui
        win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
    except Exception:
        pass


def selftest():
    """The opt-in switch with no Hangul: off with no variable, off for a value that is not in the registry."""
    class Fake:
        def RegisterModule(self, a, b):
            raise AssertionError('RegisterModule must not be called')
    old = {k: os.environ.pop(k, None) for k in ('HWPX_DOCS_SECURITY_MODULE', 'HWPX_DOCS_MODULE')}
    try:
        assert security_module(Fake()) is False
        os.environ['HWPX_DOCS_SECURITY_MODULE'] = 'hwpx_docs_selftest_no_such_value'
        assert security_module(Fake()) is False
    finally:
        os.environ.pop('HWPX_DOCS_SECURITY_MODULE', None)
        os.environ.update({k: v for k, v in old.items() if v is not None})
    print('HWPCOM SELFTEST PASS')


def _hwp_pids():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Hwp.exe', '/FO', 'CSV', '/NH'],
                         capture_output=True, text=True, encoding='mbcs', errors='replace').stdout
    return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"Hwp.exe"')}


def dialogs(pid, with_handle=False):
    """Visible top-level windows of process `pid` with their child texts (what blocks Hangul)."""
    try:
        import win32gui
        import win32process
    except ImportError:
        return []
    out = []

    def child(hwnd, texts):
        t = win32gui.GetWindowText(hwnd)
        if t:
            texts.append(t)
        return True

    def top(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32process.GetWindowThreadProcessId(hwnd)[1] == pid:
            texts = []
            try:
                win32gui.EnumChildWindows(hwnd, child, texts)
            except Exception:
                pass
            item = (win32gui.GetClassName(hwnd), win32gui.GetWindowText(hwnd), texts[:12])
            out.append(item + (hwnd,) if with_handle else item)
        return True
    win32gui.EnumWindows(top, None)
    return out


def _capture(hwnd, path):
    """Save an image of one window (diagnostics for popups)."""
    try:
        from ctypes import windll
        import win32gui
        import win32ui
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        hdc = win32gui.GetWindowDC(hwnd)
        src = win32ui.CreateDCFromHandle(hdc)
        mem = src.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(src, right - left, bottom - top)
        mem.SelectObject(bmp)
        windll.user32.PrintWindow(hwnd, mem.GetSafeHdc(), 2)
        bmp.SaveBitmapFile(mem, path)
        win32gui.ReleaseDC(hwnd, hdc)
    except Exception as e:
        print('capture failed', e)


class Hwp:
    def __init__(self, timeout=120, visible=False, prompt_wait=300):
        self.timeout, self.visible, self.prompt_wait = timeout, visible, prompt_wait
        self.pid, self.hwp, self._deadline, self.killed, self.blocked_by = None, None, None, False, None
        self.closed = []   # popups that the watchdog closed: (class, title, texts)
        self.temps = []    # temp files of save(); removed on exit
        self._first_seen = {}
        self._opening = False          # True during Open(): a popup then is the file-access prompt
        self.prompted = set()          # access prompts shown to the user (window handles)
        self.prompt_timeout = False    # the user did not answer an access prompt in time

    # ---- session -------------------------------------------------------------------------
    def __enter__(self):
        import win32com.client as win32
        self.hwp = win32.DispatchEx('HWPFrame.HwpObject')
        self.security = security_module(self.hwp)             # opt-in; right after DispatchEx, before any Open
        win = self.hwp.XHwpWindows.Item(0)
        # The PID comes from this instance's own window, so a Hangul that the user opens at the
        # same moment is never taken for ours (and never killed).
        import win32process
        self.main_hwnd = win.WindowHandle
        self.pid = win32process.GetWindowThreadProcessId(self.main_hwnd)[1]
        win.Visible = self.visible
        if not self.visible:
            _hide(self.main_hwnd)          # COM has no "start hidden": hide at the first moment we hold the window
        # Answer message boxes automatically, so a hidden box cannot block:
        # 0x1 = OK (MB_OK), 0x10 = OK (MB_OKCANCEL), 0x2000 = No (YESNOCANCEL), 0x20000 = No (YESNO).
        # A repair question gets "No", so Open() of a damaged file returns False (see open()).
        self.hwp.SetMessageBoxMode(0x00022011)
        self._hidden = {}                  # popups hidden by the watchdog: hwnd -> (first seen, class, title, texts)
        self._stop = threading.Event()
        threading.Thread(target=self._watch, daemon=True).start()
        return self

    def _watch(self):
        while not self._stop.wait(0.2):
            if not self.visible and self.pid:
                # The Hangul window is hidden, so any visible window of this process is a popup
                # (seen: a WPF notice window on the first SaveAs of a new instance). It is hidden at once
                # (no activation); one that still exists after 8 s is closed. A short progress window during
                # SaveAs is only hidden, never closed (closing it cancels the save; no file is written).
                now = time.time()
                seen = {}
                self._close_hidden(now)
                for cls, title, texts, hwnd in dialogs(self.pid, with_handle=True):
                    if hwnd == self.main_hwnd or title.endswith(' - 한글'):
                        _hide(hwnd)        # our own document window became visible (seen after some actions)
                        continue
                    if not self._opening:
                        if hwnd not in self._hidden:
                            shot = os.path.join(tempfile.gettempdir(), f'hwpcom_popup_{self.pid}_{len(self._hidden) + 1}.bmp')
                            _capture(hwnd, shot)                    # the evidence first, then out of the user's way
                            self._hidden[hwnd] = (now, cls, title, texts)
                            print('HANGUL POPUP hidden (image saved):', shot, flush=True)
                        _hide(hwnd)                                 # again if Hangul shows it again
                        continue
                    seen[hwnd] = self._first_seen.get(hwnd, now)
                    if self._opening and not self.prompt_timeout:
                        # Hangul's file-access prompt (a WPF window: its text cannot be read). Only the user
                        # answers it; keep the Open() call alive while the user decides.
                        if hwnd not in self.prompted:
                            self.prompted.add(hwnd)
                            print(f'HANGUL ACCESS PROMPT: answer it in the Hangul window ("모두 허용" = allow '
                                  f'this session); waiting up to {self.prompt_wait} s', flush=True)
                        if now - seen[hwnd] < self.prompt_wait:
                            self._deadline = max(self._deadline or 0, time.time() + 30)
                            continue
                        self.prompt_timeout = True      # no answer: close it (= deny); the batch stops
                        print('HANGUL ACCESS PROMPT: no answer; closed (= deny)', flush=True)
                    elif now - seen[hwnd] < 8:
                        continue
                    if (cls, title, texts) not in self.closed:
                        self.closed.append((cls, title, texts))
                        shot = os.path.join(tempfile.gettempdir(), f'hwpcom_popup_{self.pid}_{len(self.closed)}.bmp')
                        _capture(hwnd, shot)
                        print('HANGUL POPUP (image saved):', shot)
                    try:
                        import win32con
                        import win32gui
                        win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                    except Exception:
                        pass
                self._first_seen = seen
            if self._deadline and time.time() > self._deadline and self.pid:
                self.blocked_by = dialogs(self.pid)
                print('HANGUL BLOCKED; visible windows:', self.blocked_by)
                subprocess.run(['taskkill', '/F', '/PID', str(self.pid)], capture_output=True)
                self.killed = True
                return

    def _close_hidden(self, now):
        """A popup that was hidden and still exists after 8 s blocks Hangul: close it (it is logged on exit)."""
        import win32con
        import win32gui
        for hwnd, (t0, cls, title, texts) in list(self._hidden.items()):
            if not win32gui.IsWindow(hwnd):
                del self._hidden[hwnd]
            elif now - t0 >= 8:
                if (cls, title, texts) not in self.closed:
                    self.closed.append((cls, title, texts))
                try:
                    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                except Exception:
                    pass
                del self._hidden[hwnd]

    def guard(self, seconds=None):
        """Restart the watchdog clock before a call that can block."""
        self._deadline = time.time() + (seconds or self.timeout)

    def __exit__(self, *exc):
        self._deadline = None
        if self.closed:
            import json
            print('HANGUL POPUPS CLOSED:', json.dumps(self.closed, ensure_ascii=True))
        try:
            if not self.killed:
                self.hwp.Clear(1)
                self.hwp.Quit()
        except Exception:
            pass
        self._stop.set()
        time.sleep(1.5)
        if self.pid and self.pid in _hwp_pids():
            subprocess.run(['taskkill', '/F', '/PID', str(self.pid)], capture_output=True)
        for t in self.temps:
            try:
                os.remove(t)
                os.rmdir(os.path.dirname(t))
            except OSError:
                pass
        return False

    # ---- small helpers -------------------------------------------------------------------
    def run(self, action):
        self.guard()
        return self.hwp.HAction.Run(action)

    def act(self, action, setname, /, **items):
        """Execute `action` with parameter set `setname` (for example 'CharShape', 'HCharShape').
        Item names may use dots for sub sets: act('PageSetup', 'HSecDef', **{'PageDef.Landscape': 1}).
        (Positional-only, so an item may be called 'name'.)"""
        self.guard()
        ps = getattr(self.hwp.HParameterSet, setname)
        self.hwp.HAction.GetDefault(action, ps.HSet)
        for key, value in items.items():
            obj = ps
            parts = key.split('.')
            for p in parts[:-1]:
                obj = getattr(obj, p)
            setattr(obj, parts[-1], value)
        return self.hwp.HAction.Execute(action, ps.HSet)

    def new(self):
        self.guard()
        self.hwp.HAction.Run('FileNew')

    def text(self, s):
        self.guard()
        ps = self.hwp.HParameterSet.HInsertText
        self.hwp.HAction.GetDefault('InsertText', ps.HSet)
        ps.Text = s
        self.hwp.HAction.Execute('InsertText', ps.HSet)

    def para(self, s=''):
        if s:
            self.text(s)
        self.run('BreakPara')

    def save(self, path, fmt='HWPX'):
        """SaveAs to a NEW unique path in a fresh temp folder, then move the file to `path`.
        Hangul 2024 can show its file-access security prompt ("한글을 이용하여 위 파일에 접근하려는
        시도...") when SaveAs targets a path that existed before (seen in this corpus run); a never-used
        path did not show it. This code never answers the prompt with "allow"; the watchdog closes it
        (= deny) and the save fails."""
        import shutil
        import uuid
        path = os.path.abspath(path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = os.path.join(tmpdir.mkdtemp('hwpcom_'), uuid.uuid4().hex + '.' + fmt.lower())
        self.temps.append(tmp)
        self.guard()
        ok = self.hwp.SaveAs(tmp, fmt, '')
        if not os.path.exists(tmp):
            return False
        shutil.copyfile(tmp, path)     # Hangul keeps the saved file open, so copy (a move fails)
        return ok

    def open(self, path, fmt='HWPX', seconds=60):
        """Open a file. Returns True only if Hangul opened it with no blocking prompt."""
        self.guard(seconds)
        self._opening = True
        try:
            ok = bool(self.hwp.Open(os.path.abspath(path), fmt, 'forceopen:true'))
            if not ok and fmt and self.security:
                # with the security module on, Hangul opened HWPX only with no format and no options (tested once)
                ok = bool(self.hwp.Open(os.path.abspath(path), '', ''))
        except Exception:
            ok = False
        finally:
            self._opening = False
        self._deadline = None
        return ok and not self.killed

    def page_images(self, out_stem, dpi=96, fmt='bmp'):
        """Write one image per page: <out_stem>_p<N>.<fmt>. Returns the list of paths."""
        paths = []
        for n in range(self.hwp.PageCount):
            p = os.path.abspath(f'{out_stem}_p{n + 1}.{fmt}')
            self.guard()
            self.hwp.CreatePageImage(p, n, dpi, 24, fmt)
            paths.append(p)
        return paths

    def mm(self, v):
        return self.hwp.MiliToHwpUnit(v)

    def pt(self, v):
        return self.hwp.PointToHwpUnit(v)

    def rgb(self, hexstr):
        h = hexstr.lstrip('#')
        return self.hwp.RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def run_jobs(items, job, timeout=90, retries=2):
    """Run job(h, item) for each item in ONE hidden Hangul (one batch: the user answers the file-access
    prompt at most once, with "모두 허용"). job returns True on success. If another blocking window had to
    be closed or Hangul was killed, start a new Hangul and try the item again, at most `retries` more
    times. If the user did not answer the access prompt, stop: the rest of the batch is False.
    Returns {item: True/False}."""
    todo, tries, result = list(items), {}, {}
    print(f'HANGUL BATCH: {len(todo)} file(s) in one Hangul; it may ask once for file access', flush=True)
    while todo:
        with Hwp(timeout=timeout) as h:
            while todo:
                item = todo[0]
                n_closed = len(h.closed)
                try:
                    h.hwp.Clear(1)
                    ok = bool(job(h, item))
                except Exception as e:
                    print('JOB ERR', item, repr(e)[:200])
                    ok = False
                if h.prompt_timeout:
                    result.update({x: False for x in todo})
                    print('STOP: the file-access prompt was not answered;', len(todo), 'file(s) not done')
                    return result
                blocked = h.killed or len(h.closed) > n_closed
                if not ok and blocked and tries.get(item, 0) < retries:
                    tries[item] = tries.get(item, 0) + 1
                    print('HANGUL BLOCKED at', item, '- new Hangul, try', tries[item] + 1)
                    break
                result[item] = ok
                todo.pop(0)
                if h.killed:
                    break
    return result
