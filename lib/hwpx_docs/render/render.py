"""Render pages to PNG, and check that Hangul opens a file with no prompt.

  python render.py hwpx <file.hwpx> [<out_dir>] [--dpi 96] [--backend preview|hangul]
                                                            page images -> <out_dir>/<stem>_p<N>.png
                                                            prints "OPEN OK <file> pages <n>" or "OPEN FAIL <file>" (Hangul), or
                                                            "PREVIEW OK <file> pages <n>" (own renderer, no Hangul: package preview)
                                                            preview (default; `auto` means the same) = own renderer, Hangul never
                                                            starts by itself; `--backend hangul` opens a safe copy (no macros, no links)
  python render.py html <file.html> [<out_dir>] [--dpi 96]   Edge print-to-PDF, then Windows.Data.Pdf -> PNG
  python render.py topng <image> <out.png>                    any image (PNG/JPG/BMP/GIF/TIFF) -> PNG (WinRT)
  python render.py side <out.png> <left.png> <right.png>      side-by-side picture (scripts/img.py)

Hangul part needs pywin32 and Hangul (scripts/hwpcom.py: new hidden instance, closed at the end).
HTML and topng need Microsoft Edge and Windows PowerShell 5.1 (WinRT); no package is installed.
"""
from ..core import tmpdir
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
from ..render import img

EDGE = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']


def hwpx_pages(paths, out_dir, dpi=96, stems=None):
    """Open each HWPX in Hangul, write PNG pages <out_dir>/<stem>_p<N>.png.
    Returns {path: [png, ...] or None if Hangul did not open it with no prompt}."""
    from ..render.hwpcom import run_jobs
    os.makedirs(out_dir, exist_ok=True)
    result = {}

    def job(h, p):
        stem = os.path.join(out_dir, (stems or {}).get(p) or os.path.splitext(os.path.basename(p))[0])
        if not h.open(p):
            print('OPEN FAIL', p)
            result[p] = None
            return False
        # A Hangul-saved file can reopen with the caret inside a table cell (settings.xml); then
        # CreatePageImage writes only that cell. Move the caret to the top of the document first.
        h.run('Cancel')
        h.hwp.MovePos(2, 0, 0)
        pngs = []
        for bmp in h.page_images(stem, dpi=dpi, fmt='bmp'):
            if os.path.exists(bmp):
                png = bmp[:-4] + '.png'
                img.save_png(png, img.load(bmp))
                os.remove(bmp)
                pngs.append(png)
        print('OPEN OK', p, 'pages', len(pngs))
        result[p] = pngs
        return True
    run_jobs(paths, job)
    return result


def _q(text):
    """A PowerShell single-quoted string literal: every quote character (' and the Unicode ‘ ’ ‚ ‛ that PowerShell also takes
    as quotes) is doubled, so a file name cannot end the string and run code."""
    return "'" + re.sub("(['‘’‚‛])", r'\1\1', str(text)) + "'"


def _ps(script):
    r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())
    return r.stdout


WINRT = r'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, $type) { $t = $asTask.MakeGenericMethod($type).Invoke($null, @($op)); $t.Wait(-1) | Out-Null; $t.Result }
function AwaitA($op) { $t = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0].Invoke($null, @($op)); $t.Wait(-1) | Out-Null }
[Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfDocument,Windows.Data.Pdf,ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream,Windows.Storage.Streams,ContentType=WindowsRuntime] | Out-Null
'''


def pdf_pages(pdf, out_stem, dpi=96):
    """PDF -> one PNG per page with Windows.Data.Pdf. Returns the PNG paths."""
    script = WINRT + rf'''
$f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync({_q(os.path.abspath(pdf))})) ([Windows.Storage.StorageFile])
$doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($f)) ([Windows.Data.Pdf.PdfDocument])
for ($i = 0; $i -lt $doc.PageCount; $i++) {{
  $page = $doc.GetPage($i)
  $opt = New-Object Windows.Data.Pdf.PdfPageRenderOptions
  $opt.DestinationWidth = [uint32][math]::Round($page.Size.Width * {dpi} / 96)
  $opt.BitmapEncoderId = [Windows.Graphics.Imaging.BitmapEncoder]::PngEncoderId
  $out = {_q(os.path.abspath(out_stem) + '_p')} + ($i + 1) + '.png'
  $fs = [System.IO.File]::Create($out)
  $ms = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  AwaitA ($page.RenderToStreamAsync($ms, $opt))
  $rs = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($ms.GetInputStreamAt(0))
  $rs.CopyTo($fs); $fs.Close()
  Write-Output $out
}}
'''
    return [line.strip() for line in _ps(script).splitlines() if line.strip().endswith('.png')]


def to_png(src, dst):
    """Any image Windows can decode (PNG, JPG, BMP, GIF, TIFF) -> 24-bit PNG that img.py reads."""
    script = WINRT + rf'''
$f = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync({_q(os.path.abspath(src))})) ([Windows.Storage.StorageFile])
$s =Await ($f.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
$dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($s)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bmp = Await ($dec.GetSoftwareBitmapAsync([Windows.Graphics.Imaging.BitmapPixelFormat]::Bgra8, [Windows.Graphics.Imaging.BitmapAlphaMode]::Ignore)) ([Windows.Graphics.Imaging.SoftwareBitmap])
$ms = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
$enc = Await ([Windows.Graphics.Imaging.BitmapEncoder]::CreateAsync([Windows.Graphics.Imaging.BitmapEncoder]::BmpEncoderId, $ms)) ([Windows.Graphics.Imaging.BitmapEncoder])
$enc.SetSoftwareBitmap($bmp)
AwaitA ($enc.FlushAsync())
$fs = [System.IO.File]::Create({_q(os.path.abspath(dst) + '.bmp')})
$rs = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($ms.GetInputStreamAt(0))
$rs.CopyTo($fs); $fs.Close()
Write-Output ($dec.DpiX)
'''
    dpi = _ps(script).strip()
    img.save_png(dst, img.load(dst + '.bmp'))
    os.remove(dst + '.bmp')
    return dpi


def html_pages(html, out_dir, dpi=96):
    edge = next((e for e in EDGE if os.path.exists(e)), None)
    if not edge:
        raise RuntimeError('Microsoft Edge not found')
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.abspath(os.path.join(out_dir, os.path.splitext(os.path.basename(html))[0] + '_web'))
    # Edge writes nothing for a non-ASCII PDF path or an un-encoded non-ASCII file URL: use an ASCII temp PDF
    # and a percent-encoded URL
    from urllib.parse import quote
    profile = tmpdir.mkdtemp('edge_render_')
    pdf = os.path.join(profile, 'page.pdf')
    url = 'file:///' + quote(os.path.abspath(html).replace('\\', '/'), safe='/:')
    # Start Edge through PowerShell Start-Process: started directly (subprocess / Git Bash) while the user's Edge
    # runs, msedge.exe exits 0 and writes nothing (seen 2026-11-14). Also needs a process outside the Bash sandbox.
    args = ','.join(_q(a) for a in ('--headless=new', '--no-first-run', '--disable-gpu', '--no-pdf-header-footer',
                                    f'--user-data-dir={profile}', f'--print-to-pdf={pdf}', url))
    import shutil
    try:            # the Edge profile (about 22 MB) is only for this print: it goes when the pages are out
        _ps(f"Start-Process -FilePath {_q(edge)} -ArgumentList {args} -Wait")
        if not os.path.exists(pdf):
            raise RuntimeError('Edge wrote no PDF (run outside the Bash sandbox; see rules.md W07)')
        pngs = []
        for n, p in enumerate(pdf_pages(pdf, os.path.join(profile, 'p'), dpi), start=1):   # ASCII paths for PowerShell
            dst = f'{stem}_p{n}.png'
            shutil.move(p, dst)
            pngs.append(dst)
        return pngs
    finally:
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == '__main__':
    args = sys.argv[1:]
    dpi = 96
    if '--dpi' in args:
        i = args.index('--dpi')
        dpi = int(args[i + 1])
        del args[i:i + 2]
    backend = 'preview'
    if '--backend' in args:
        i = args.index('--backend')
        backend = args[i + 1]
        del args[i:i + 2]
    cmd = args[0]
    if cmd == 'hwpx':
        out = args[2] if len(args) > 2 else os.path.dirname(os.path.abspath(args[1]))
        backend = 'preview' if backend == 'auto' else backend
        if backend == 'hangul':
            hwpx_pages([args[1]], out, dpi)
        else:
            from ..core import registry
            fn = registry.backend('render', backend)
            if fn is None:
                sys.exit('unknown backend: ' + backend)
            fn(args[1], out, dpi)
    elif cmd == 'html':
        out = args[2] if len(args) > 2 else os.path.dirname(os.path.abspath(args[1]))
        for p in html_pages(args[1], out, dpi):
            print('PAGE', p)
    elif cmd == 'topng':
        print('DPI', to_png(args[1], args[2]))
    elif cmd == 'side':
        img.save_png(args[1], img.side_by_side([img.load(p) for p in args[2:]]))
        print('SIDE', args[1])
