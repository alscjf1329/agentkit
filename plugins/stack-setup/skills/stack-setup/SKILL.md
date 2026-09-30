---
name: stack-setup
description: 프로젝트 언어/프레임워크를 감지하거나 입력받아, 주간 GitHub 트렌드 인덱스 기준으로 스킬·플러그인·MCP를 카테고리별 추천하고 사용자가 고른 것만 검토 후 설치한다. "AI 세팅", "스킬 추천", "플러그인 추천", "새 프로젝트 세팅", "/stack-setup" 요청 시 사용.
---

# Stack Setup

새 프로젝트에 맞는 AI 스킬/플러그인을 **최신 트렌드 기준**으로 추천·설치한다.
원칙: 적게, 검증된 것만, 카테고리당 1개.

## 0. 준비 (매번 먼저)

**스크립트 경로**: 이 스킬이 로드될 때 표시되는 "Base directory for this skill" 경로를 `SKILL_DIR` 로 쓴다.
스크립트는 `SKILL_DIR/scripts/` 에 있다. (환경변수 치환에 의존하지 말 것)
경로를 못 찾으면 `~/.claude/plugins/` 아래에서 `stack-setup/scripts/recommend.py` 를 검색.

**파이썬 명령**: 아래 순서로 `--version` 을 실행해 출력에 `Python 3` 이 나오는 첫 번째를 `PY` 로 쓴다.
1. `python3`  2. `python`  3. `py -3`
(윈도우의 `python3` 는 스토어 바로가기라 아무 출력 없이 끝날 수 있음 → 출력 확인 필수)
셋 다 없으면 사용자에게 Python 3.8+ 설치를 안내하고 중단.

경로에 공백이 있을 수 있으니 스크립트 경로는 항상 따옴표로 감싼다.

## 1. 스택 확정

```bash
PY "SKILL_DIR/scripts/detect_stack.py" .
```

- 루트 + 1단계 하위 폴더(모노레포)까지 감지. `evidence` 로 근거 표시.
- 사용자가 스택을 말했으면 그게 우선.
- `empty: true` (신규 프로젝트) 면 AskUserQuestion 으로 질문 (multiSelect):
  `spring+java` / `nextjs+typescript` / `nestjs+typescript` / `python+fastapi` (+ 직접 입력)
- 감지 결과가 있으면 한 줄로 확인: "감지된 스택: spring, oracle — 맞아?"

## 2. 추천 받기

```bash
PY "SKILL_DIR/scripts/recommend.py" --stacks <콤마구분> --project . --top 3
```

- 이미 설치한 것(`.claude/stack-setup.lock.json`)은 자동 제외.
  lock 에 없지만 설치돼 있는 게 보이면(`/plugin` 목록, `.claude/skills/`) `--installed owner/repo,...` 로 추가.
- `stale: true` 면 "트렌드 인덱스가 N일 지남" 경고 먼저.
- `index_source: bundled` 면 "원격 인덱스 못 받아서 번들 사본 사용" 안내.

## 3. 보여주기

카테고리별 표. 컬럼: 레포 | 종류 | 최근7일★ | 총★ | 마지막 커밋 | 스택매칭 | 한줄설명
- `growth_method` 가 `estimate` 면 최근7일★ 옆에 "(추정)"
- `official: true` → "공식"
- `risk` 중 true 인 항목은 ⚠ 로 표시 (hooks / scripts / no_license / new_repo)
- 카테고리당 **1개만** 고르도록 안내. 같은 기능이 anthropics/claude-plugins-official 에 있으면 그걸 먼저 제안.
- 추천이 비었으면: 스택 매칭 결과 없음을 알리고 범용 카테고리만 보여줌.

## 4. 설치 전 검토 (필수)

고른 항목마다 WebFetch 로 레포를 확인:
- `risk.hooks` → hooks 설정 파일을 열어 실행되는 셸 명령을 한 줄씩 요약
- `risk.scripts` → 스크립트 안의 네트워크 호출, `rm -rf`, `curl | sh`, 홈 디렉토리/시크릿 접근 여부
- MCP → 필요한 API 키·권한
- `no_license` / `new_repo` → 경고

위험 요소가 있으면 명시하고 사용자 재확인 후에만 진행.

## 5. 설치

범위 질문: 이 프로젝트(기본) vs 전역.
인덱스의 `install` 배열이 실제 레포 구조에서 뽑은 명령이다. 그대로 사용:

| 종류 | 명령 |
|---|---|
| plugin | `/plugin marketplace add <repo>` → `/plugin install <plugin>@<marketplace>` — 슬래시 명령은 사용자가 입력해야 하므로 복사할 명령을 제시. 프로젝트 범위면 `claude plugin install <plugin>@<marketplace> --scope project` 를 셸로 실행 가능 |
| skill | `npx skills add <repo>` (여러 스킬 레포면 `--skill <이름>`, 전역이면 `--global`) |
| mcp | README 설치법대로 `.mcp.json` 에 추가. 키는 `${ENV}` 참조로 쓰고 `.env` + `.gitignore` 확인 |

설치 성공한 것만 기록:
```bash
PY "SKILL_DIR/scripts/lock.py" add --repo <owner/repo> --kind <plugin|skill|mcp> --scope <project|user> --cmd "<실행한 명령>"
```

## 6. 마무리

- `AGENTS.md` 의 `<...>` (스택, 빌드/테스트/린트 명령)가 비어 있으면 감지된 스택 기준으로 채우자고 제안
- 설치 목록 + 각 스킬을 트리거하는 예시 문장 한 줄씩
- 제거하려면: 해당 제거 명령 실행 후 `lock.py remove --repo <owner/repo>`
