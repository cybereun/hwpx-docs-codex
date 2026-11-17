# 릴리스 이력

## [v1.0.1](https://github.com/cybereun/hwpx-docs-codex/releases/tag/v1.0.1) (2026-11-17)

- 한글 설치 없이 HWP 5.0 문서를 읽고, 편집하고, 생성하며 HWPX와 양방향으로 변환할 수 있습니다. [명령별 지원 범위](docs/hwp-parity.md)
- 외부 문서의 자동 렌더링에 내장 미리보기를 사용합니다. 한글 렌더링을 요청하면 스크립트와 외부 그림 링크를 제거한 사본을 사용합니다. 문서 압축 해제에 크기 제한을 적용합니다.
- 일반 표는 기본적으로 글자처럼 취급합니다. 긴 표와 반복 머리행이 있는 표는 쪽 사이에서 나뉩니다. 기존의 흐르는 표 배치가 필요하면 스펙에 `"inline": false`를 지정하세요.
- 법령 별지 서식 153개에서 추출한 여백, 글꼴, 접수란, 서명란을 양식 팩으로 제공합니다. [양식 팩 사용법](addons/hwpx-docs-forms/README.md)
- Windows DPAPI 금고를 사용하는 가명화 및 복원 기능을 추가했습니다. 동시 읽기에서 토큰이 섞이지 않도록 금고 갱신을 직렬화하고, JSON의 유니코드 이스케이프로 저장된 토큰도 복원합니다. 보호 범위는 `hd` 명령의 처리 경로입니다. [개인정보 사용법](addons/hwpx-docs-privacy/README.md)
- `python lib/hd.py --version`으로 Codex 포트 버전을 확인할 수 있습니다.

한글 2024에서 생성한 HWP와 HWPX 신청서를 열었으며, 형식에 따라 일부 표 안쪽 선이 다르게 표시됐습니다. HWPX 샘플 271개의 왕복 검사를 통과했습니다. 계획서 `gyehoekseo`의 미리보기 이미지 비교 1건은 이 버전, 이전 Codex 커밋, 포트의 원본 커밋에서 동일하게 허용 오차를 넘었습니다.

## 초기 Codex 포트 (2026-11-17)

- HWPX 엔진과 전문 가이드를 Codex 스킬로 포팅했습니다.
- 한국어 README와 Windows, macOS, Linux 설치 방법을 추가했습니다.
- 기준 커밋은 [9d3f517](https://github.com/cybereun/hwpx-docs-codex/commit/9d3f51766b4ee944cf7892a360a765079b093457)입니다.
