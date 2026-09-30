---
name: stack-setup
description: 프로젝트 언어/프레임워크를 감지하거나 입력받아, 주간 GitHub 트렌드 인덱스 기준으로 스킬·플러그인·MCP를 카테고리별 추천하고 사용자가 고른 것만 검토 후 설치한다. "AI 세팅", "스킬 추천", "플러그인 추천", "새 프로젝트 세팅", "/stack-setup" 요청 시 사용.
---

# Stack Setup

새 프로젝트에 맞는 AI 스킬/플러그인을 **최신 트렌드 기준**으로 추천·설치한다.
원칙: 적게, 검증된 것만, 카테고리당 1개.

## 1. 스택 확정

1. 현재 디렉토리 감지:
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/detect_stack.py" .
   ```
2. 결과가 비었거나(신규 프로젝트) 사용자가 스택을 말했으면 그걸 우선.
3. 사용자에게 한 줄로 확인: "감지된 스택: spring, oracle — 맞아?" (AskUserQuestion 있으면 사용)

## 2. 이미 설치된 것 파악

- `~/.claude/plugins/`, `~/.claude/skills/`, `./.claude/skills/`, `.mcp.json` 확인
- 설치된 레포명을 콤마로 모아 `--installed` 에 전달

## 3. 추천 받기

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/recommend.py" --stacks <콤마구분> --installed <콤마구분> --top 3
```

- 인덱스는 GitHub Actions가 매주 갱신 (`AI_SETUP_INDEX_URL`), 실패 시 번들 사본 사용
- `index_generated_at` 이 21일 이상 지났으면 "인덱스 오래됨" 경고

## 4. 사용자에게 보여주기

카테고리별 표로. 컬럼: 레포 | 종류 | 주간★ | 총★ | 마지막 커밋 | 스택매칭 | 한줄설명
- `growth_measured: false` 면 주간★ 옆에 "(추정)" 표기
- `official: true` 는 "공식" 뱃지
- 카테고리당 **1개만** 고르도록 안내 (기능 중복·컨텍스트 낭비 방지)
- 공식 anthropics/claude-plugins-official 에 같은 기능 있으면 그걸 먼저 제안

## 5. 설치 전 검토 (필수, 건너뛰지 말 것)

사용자가 고른 각 항목에 대해 WebFetch 로 레포 확인:
- `hooks` / `.claude/settings.json` 의 훅 명령 → 무슨 셸 명령 실행하는지 요약
- `scripts/` 내 네트워크 호출, `rm -rf`, `curl | sh`, 시크릿 읽기 여부
- MCP 서버면 필요한 API 키·권한
- 라이선스 없음 / 30일 내 생성된 신규 레포는 경고

위험 요소 있으면 설치 전에 사용자에게 명시하고 재확인.

## 6. 설치

범위 먼저 물어봄: 글로벌(`~/.claude`) vs 이 프로젝트(`.claude`). 기본은 프로젝트.

| 종류 | 명령 |
|---|---|
| plugin | `/plugin marketplace add <repo>` → `/plugin install <name>@<marketplace>` (사용자가 직접 입력해야 하면 명령 안내) |
| skill | `npx skills add <repo> [--global]` |
| mcp | README 의 설치법 따라 `.mcp.json` 추가, 키는 `.env` 참조 + `.gitignore` 확인 |

## 7. 기록 & 마무리

- `.claude/stack-setup.lock.json` 에 기록: `{repo, kind, scope, installed_at, commit_sha(가능하면)}`
  → 다음 실행 때 `--installed` 로 재사용, 롤백 근거
- `CLAUDE.md` 없으면 스택 기반 최소 템플릿 생성 제안 (빌드/테스트/린트 명령, 컨벤션)
- 끝나면 설치 목록 + 트리거 확인 방법 한 줄씩
