"""Regression test for the Codex CLI using synthetic email addresses and a temporary vault."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[2]
HD = ROOT / 'lib/hd.py'
PV = ROOT / 'addons/hwpx-docs-privacy/scripts/pv.py'
VALUES = [f'synthetic-{i}@example.com' for i in range(6)]


def main():
    with tempfile.TemporaryDirectory(prefix='hwpx-codex-privacy-') as folder:
        work = Path(folder)
        config = work / 'addons.json'
        env = dict(os.environ, HWPX_DOCS_ADDONS_CONFIG=str(config),
                   HWPX_PRIVACY_HOME=str(work / 'vault'), PYTHONUTF8='1')
        for key in ('HWPX_DOCS_ADDONS', 'HWPX_PRIVACY_BACKEND', 'HWPX_PRIVACY_PASSPHRASE'):
            env.pop(key, None)

        def run(script, *args, expected=0):
            result = subprocess.run([sys.executable, str(script), *args], cwd=work, env=env,
                                    capture_output=True, encoding='utf-8', timeout=60)
            assert result.returncode == expected, (args, result.returncode, result.stdout, result.stderr)
            return result.stdout

        def write_spec(name, value):
            (work / name).write_text(json.dumps({'body': [{'p': f'이메일: {value}'}]}), encoding='utf-8')

        for i, value in enumerate(VALUES):
            write_spec(f'{i}.json', value)
            run(HD, 'build', f'{i}.json', f'{i}.hwpx')
        run(PV, 'enable')
        with ThreadPoolExecutor(max_workers=len(VALUES)) as executor:
            outputs = list(executor.map(lambda i: run(HD, 'text', f'{i}.hwpx'), range(len(VALUES))))

        tags = []
        for value, output in zip(VALUES, outputs):
            tag = re.search(r'⟪이메일\d+⟫', output)
            assert tag and value not in output
            tags.append(tag.group())
        assert len(set(tags)) == len(VALUES), tags
        backend = 'dpapi' if os.name == 'nt' else 'file'
        status = run(PV, 'status')
        assert f'vault backend {backend}' in status and f'{len(VALUES)} tags' in status

        for tag, value in zip(tags, VALUES):
            write_spec('restore.json', tag)
            run(HD, 'build', 'restore.json', 'restored.hwpx')
            with zipfile.ZipFile(work / 'restored.hwpx') as package:
                section = package.read('Contents/section0.xml').decode('utf-8')
            assert value in section and tag not in section

        config.write_text('{"addons":["missing"],"enforce":true}', encoding='utf-8')
        assert 'PRIVACY ADDON NOT LOADED' in run(HD, 'text', '0.hwpx', expected=2)
    print('CODEX PRIVACY REGRESSION TEST PASS')


if __name__ == '__main__':
    main()
