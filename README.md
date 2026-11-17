# HWPX Docs for Codex

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-5B5BD6)](https://github.com/cybereun/hwpx-docs-codex)
[![HWPX](https://img.shields.io/badge/Format-HWPX-2D8CFF)](https://github.com/cybereun/hwpx-docs-codex)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-AGPL--3.0--or--later-blue)](LICENSE)

Codex에서 한컴오피스 한글용 HWPX 문서를 만들고, 읽고, 수정하고, 검사할 수 있는 스킬입니다. JSON 스펙으로 문서를 구성하며, 표·도형·그림·차트와 페이지 설정을 지원합니다.

이 저장소는 [BlackBuddle/hwpx-docs](https://github.com/BlackBuddle/hwpx-docs)를 Codex에서 사용할 수 있도록 포팅한 프로젝트입니다. 원본 엔진과 전문 가이드의 출처 및 라이선스는 [NOTICE.md](NOTICE.md)를 확인해 주세요.

## 주요 기능

Codex 포트 버전은 **v1.0.1**입니다. `python lib/hd.py --version`으로 확인할 수 있습니다. 버전별 변경 사항은 [릴리스 이력](CHANGELOG.md)에 기록합니다.

- 외부 문서는 기본적으로 내장 미리보기로 열고, 한글 렌더링을 명시적으로 요청하면 스크립트를 제거한 사본을 사용합니다. 문서를 읽을 때 압축 해제 크기를 제한합니다.
- 한글 설치 없이 HWP 5.0 읽기, 양식 편집, 생성과 HWPX 변환을 지원합니다. [명령별 지원 범위와 변환 한계](docs/hwp-parity.md)를 확인할 수 있습니다.
- 일반 표는 기본적으로 글자처럼 취급합니다. 쪽을 넘기는 긴 표나 머리 행을 반복하는 표는 흐르는 표가 됩니다. 기존 배치가 필요하면 스펙에서 `"inline": false`를 지정하세요.
- 관공서 양식의 여백·글꼴·접수란·서명란을 재사용할 수 있습니다. [관공서 양식 팩](addons/hwpx-docs-forms/README.md)
- Windows에서 개인정보 가명화와 로컬 복원을 선택적으로 사용할 수 있습니다. [Codex 개인정보 사용법](addons/hwpx-docs-privacy/README.md)

- JSON 스펙으로 HWPX 문서를 만들고, 기존 HWPX를 읽어 다시 편집합니다.
- 받은 신청서나 양식을 채우고, 문서의 텍스트를 Markdown으로 추출합니다.
- Markdown·HTML을 HWPX로 변환하고, 표·도형·그림·한글 차트를 넣습니다.
- 용지 크기, 여백, 다단, 머리말·꼬리말, 쪽 번호를 설정합니다.
- 문서 구조와 가독성을 확인하고, 한글 또는 내장 미리보기로 페이지를 확인합니다.
- 요청에 따라 개인정보 가리기, 문서 암호·배포용 문서를 처리합니다.

스킬은 공통 안내와 11개 전문 가이드로 구성되어 있습니다. 세부 주제는 [skills/](skills/)에서 확인할 수 있습니다.

## Codex 설치

Python 3.10 이상이 필요합니다. 기본 설치 경로는 `~/.codex/skills/hwpx-docs`이며, `CODEX_HOME`이 지정되어 있으면 `$CODEX_HOME/skills/hwpx-docs`를 사용합니다.

### Windows PowerShell

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$skillsDir = Join-Path $codexHome 'skills'
New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null
git clone https://github.com/cybereun/hwpx-docs-codex.git (Join-Path $skillsDir 'hwpx-docs')
```

### macOS / Linux

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/cybereun/hwpx-docs-codex.git "${CODEX_HOME:-$HOME/.codex}/skills/hwpx-docs"
```

저장소를 이미 내려받았다면 Windows에서는 `.\install.ps1`, macOS/Linux에서는 `bash install.sh`를 실행해 설치할 수도 있습니다. 설치 후 새 Codex 세션을 열고 “이 내용을 한 페이지 HWPX로 만들어줘”처럼 요청하면 됩니다. 스킬은 `SKILL.md`가 있는 폴더 전체를 함께 설치해야 실행 코드와 문서 참조가 유지됩니다.

Git으로 설치했다면 설치 폴더에서 `git pull --ff-only`로 업데이트할 수 있습니다. 설치 스크립트로 복사한 경우 기존 폴더를 백업한 뒤 새 버전의 설치 스크립트를 실행하세요.

### 필요한 환경

- Python 3.10 이상: 문서 생성·읽기·수정·대부분의 검사
- 한컴오피스 한글이 설치된 Windows: 한글에서 렌더링, COM 기반 PDF 저장, 문서 암호·배포용 문서 처리
- 한글이 없는 환경에서도 내장 미리보기와 기본 HWPX 작업을 사용할 수 있습니다.

## 개발자 및 문의

- Codex 포트 및 유지관리: [Lebi (@cybereun)](https://github.com/cybereun)
- 문의와 버그 제보: [GitHub Issues](https://github.com/cybereun/hwpx-docs-codex/issues)
- 원본 프로젝트 및 엔진: [BlackBuddle/hwpx-docs](https://github.com/BlackBuddle/hwpx-docs)

Codex 포트의 개발자 정보는 이 저장소의 변경분을 가리킵니다. 원본 엔진·문서·예제의 저작권과 출처는 원저작자에게 있습니다.

## 라이선스와 배포

이 프로젝트에는 원본 `hwpx-docs`의 엔진, 가이드, 예제와 자료가 포함되어 있으며 `AGPL-3.0-or-later` 조건으로 배포됩니다. 재배포할 때는 LICENSE와 원본 출처 고지를 함께 유지하고, 수정·배포하는 버전도 해당 AGPL 조건을 지켜 주세요. 자세한 내용은 [LICENSE](LICENSE)와 [NOTICE.md](NOTICE.md)를 확인하세요.
