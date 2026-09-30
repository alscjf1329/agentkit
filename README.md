# agentkit

> 새 프로젝트는 [agentkit-template](https://github.com/alscjf1329/agentkit-template) 로 시작하면 이 플러그인이 자동 등록됨.

프로젝트 스택 정해지면 → **이번 주 GitHub 트렌드 기준**으로 스킬/플러그인/MCP 추천 → 검토 후 설치.

## 구조

```
.github/workflows/update-index.yml   매주 월 09:00 KST 크롤링 (GitHub Actions)
crawler/crawl.py                     GitHub 검색 → 태깅 → 트렌드 점수 → index/index.json
crawler/stacks.json                  스택·카테고리 키워드, 검색 쿼리 (여기만 고치면 튜닝됨)
index/index.json                     생성된 인덱스
.claude-plugin/marketplace.json      이 레포 = Claude Code 마켓플레이스
plugins/stack-setup/skills/stack-setup/
  SKILL.md                           추천·검토·설치 절차
  scripts/detect_stack.py            build.gradle / package.json 등으로 스택 감지 (모노레포 1단계 포함)
  scripts/recommend.py               인덱스에서 카테고리별 Top N (lock 파일 기준 설치된 것 제외)
  scripts/lock.py                    설치 기록 (.claude/stack-setup.lock.json)
  data/index.json                    인덱스 번들 사본 (오프라인 fallback)
```

## 트렌드 점수

```
score = log(최근 7일 스타) * 3     ← 메인: 지금 뜨는 정도
      + log(총 스타) * 0.5         ← 규모
      + exp(-마지막커밋일/30) * 2   ← 활발함
      + 공식(anthropics) 3
```
- 최근 7일 스타는 stargazers API 타임스탬프로 **첫 실행부터 실측** (`growth_method: stargazers`)
  - API 한도 걸리면 지난 인덱스 대비(`snapshot`) → 그것도 없으면 평균 속도 추정(`estimate`)
- 레포 파일트리로 **실제 구성 확인**: `.claude-plugin/marketplace.json` / `SKILL.md` / MCP 설정
  - 셋 다 없는 레포(awesome 리스트 등)는 제외
  - 설치 명령(`install`)은 실제 마켓 이름·플러그인 이름·스킬 이름으로 생성
- 위험 플래그(`risk`): hooks, 실행 스크립트, 라이선스 없음, 생성 30일 미만
- 스택 태깅: 설명 + topics + **스킬/플러그인 폴더명** (레포 주 언어는 오태깅 원인이라 안 씀)
- 120일 이상 커밋 없음, 아카이브, 포크, 스타 20 미만은 제외
- 상세 조사는 1차 점수 상위 150개만 (GITHUB_TOKEN 시간당 1000회 한도)

## 셋업

1. Actions 탭 → `update-trend-index` → **Run workflow** (첫 인덱스 생성)
2. Claude Code에서 (또는 agentkit-template 쓰면 자동):
   ```
   /plugin marketplace add alscjf1329/agentkit
   /plugin install stack-setup@agentkit
   ```
3. 새 프로젝트에서 `/stack-setup` 또는 "AI 세팅해줘"

## 로컬 테스트

```bash
GITHUB_TOKEN=$(gh auth token) python3 crawler/crawl.py
python3 plugins/stack-setup/skills/stack-setup/scripts/detect_stack.py ~/my-project
python3 plugins/stack-setup/skills/stack-setup/scripts/recommend.py --stacks spring,oracle --index index/index.json
```

윈도우: `python3` 대신 `python` 또는 `py -3`. 스킬은 셋 중 되는 걸 자동으로 고름.

## TODO
- 설치 수 지표 반영 (claude-plugins.dev / skills.sh)
- 카테고리 태깅 LLM 보정 (키워드 매칭 한계)
