# ai-stack-setup

> 새 프로젝트는 [project-template](https://github.com/alscjf1329/project-template) 로 시작하면 이 플러그인이 자동 등록됨.

프로젝트 스택 정해지면 → **이번 주 GitHub 트렌드 기준**으로 스킬/플러그인/MCP 추천 → 검토 후 설치.

## 구조

```
.github/workflows/update-index.yml   매주 월 09:00 KST 크롤링 (GitHub Actions)
crawler/crawl.py                     GitHub 검색 → 태깅 → 트렌드 점수 → index/index.json
crawler/stacks.json                  스택·카테고리 키워드, 검색 쿼리 (여기만 고치면 튜닝됨)
index/index.json                     생성된 인덱스
.claude-plugin/marketplace.json      이 레포 = Claude Code 마켓플레이스
plugins/stack-setup/
  skills/stack-setup/SKILL.md        추천·검토·설치 절차
  scripts/detect_stack.py            build.gradle / package.json 등으로 스택 감지
  scripts/recommend.py               인덱스에서 카테고리별 Top N
  data/index.json                    인덱스 번들 사본 (오프라인 fallback)
```

## 트렌드 점수

```
score = log(주간 스타 증가) * 3   ← 메인: 지금 뜨는 정도
      + log(총 스타) * 0.5         ← 규모
      + exp(-마지막커밋일/30) * 2   ← 활발함
      + 공식(anthropics) 3
```
주간 증가는 지난 스냅샷 대비 실측. 첫 실행 땐 이력이 없어 `스타/레포나이`로 추정 (`growth_measured:false`).
120일 이상 커밋 없음, 아카이브, 포크, 스타 20 미만은 제외.

## 셋업

1. Actions 탭 → `update-trend-index` → **Run workflow** (첫 인덱스 생성)
2. Claude Code에서 (또는 project-template 쓰면 자동):
   ```
   /plugin marketplace add alscjf1329/ai-stack-setup
   /plugin install stack-setup@sheepduck-ai-setup
   ```
3. 새 프로젝트에서 `/stack-setup` 또는 "AI 세팅해줘"

## 로컬 테스트

```bash
GITHUB_TOKEN=$(gh auth token) python3 crawler/crawl.py
python3 plugins/stack-setup/scripts/detect_stack.py ~/my-project
python3 plugins/stack-setup/scripts/recommend.py --stacks spring,oracle --index index/index.json
```

## TODO (다음 단계)
- 스킬 레포 실제 설치 수 반영 (claude-plugins.dev / skills.sh 데이터)
- README 기반 설치 명령 자동 추출 (현재 kind 추정 + 기본 명령)
- 카테고리 태깅 LLM 보정 (키워드 매칭 한계)
