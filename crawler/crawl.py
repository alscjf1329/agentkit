#!/usr/bin/env python3
"""
트렌드 인덱스 생성기.
GitHub 검색 → 스택/카테고리 태깅 → 트렌드 점수 계산 → index/index.json

트렌드 점수 핵심: 누적 스타가 아니라 '지난 스냅샷 대비 증가량'.
이전 index.json 의 stars 를 기억해뒀다가 다음 실행에서 delta 계산.
(첫 실행은 이력 없으니 스타/레포나이 로 근사)

환경변수: GITHUB_TOKEN (Actions 에선 자동 제공)
사용: python crawler/crawl.py [--fixture path.json]  # fixture = 오프라인 테스트용
"""
import json, math, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "crawler", "stacks.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "index", "index.json")
NOW = datetime.now(timezone.utc)

MIN_STARS = 20          # 노이즈 컷
STALE_DAYS = 120        # 이 기간 커밋 없으면 제외
PER_QUERY_PAGES = 3     # 쿼리당 100 x 3


def gh_search(q, page):
    url = "https://api.github.com/search/repositories?" + urllib.parse.urlencode(
        {"q": f"{q} stars:>={MIN_STARS}", "sort": "updated", "order": "desc",
         "per_page": 100, "page": page})
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "ai-stack-setup-crawler",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("items", [])


def fetch_all():
    seen = {}
    for q in CFG["queries"]:
        for p in range(1, PER_QUERY_PAGES + 1):
            try:
                items = gh_search(q, p)
            except Exception as e:
                print(f"[warn] {q} p{p}: {e}", file=sys.stderr)
                break
            for it in items:
                seen[it["full_name"]] = it
            if len(items) < 100:
                break
            time.sleep(2.5)  # search API: 30 req/min (auth)
    return list(seen.values())


def days_since(iso):
    return max((NOW - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days, 0)


def tag(text, table):
    toks = set(text.replace("/", " ").replace("_", "-").split()) | {text}
    hits = []
    for key, kws in table.items():
        for kw in kws:
            # 짧은 키워드(ts, go 등)는 토큰 일치만, 긴 건 부분일치 허용
            if (len(kw) <= 3 and kw in toks) or (len(kw) > 3 and kw in text):
                hits.append(key); break
    return hits


def detect_kind(r):
    text = " ".join([r.get("description") or "", " ".join(r.get("topics", []))]).lower()
    if "marketplace" in text or "plugin" in text:
        return "plugin"
    if "mcp" in text:
        return "mcp"
    return "skill"


def install_hint(r, kind):
    name = r["full_name"]
    if kind == "plugin":
        return f"/plugin marketplace add {name}"
    if kind == "mcp":
        return f"# README 확인: https://github.com/{name}"
    return f"npx skills add {name}"


def build(repos, prev):
    prev_map = {e["repo"]: e for e in prev.get("entries", [])}
    prev_at = prev.get("generated_at")
    gap_days = days_since(prev_at) if prev_at else None
    out = []
    for r in repos:
        if r.get("archived") or r.get("fork"):
            continue
        pushed = days_since(r["pushed_at"])
        if pushed > STALE_DAYS:
            continue
        stars = r["stargazers_count"]
        age = max(days_since(r["created_at"]), 1)
        text = " ".join([r["name"], r.get("description") or "", " ".join(r.get("topics", []))]).lower()

        # 주간 스타 증가량 (이력 있으면 실측, 없으면 평균 속도로 근사)
        p = prev_map.get(r["full_name"])
        if p and gap_days:
            weekly = (stars - p["stars"]) * 7 / gap_days
            measured = True
        else:
            weekly = stars * 7 / age
            measured = False

        official = r["owner"]["login"] in CFG["official_owners"]
        recency = math.exp(-pushed / 30)             # 최근 커밋일수록 1에 가까움
        score = (math.log1p(max(weekly, 0)) * 3      # 성장 속도 (메인)
                 + math.log1p(stars) * 0.5           # 규모 (보조)
                 + recency * 2                       # 활발함
                 + (3 if official else 0))           # 공식 가산점

        kind = detect_kind(r)
        out.append({
            "repo": r["full_name"],
            "url": r["html_url"],
            "description": (r.get("description") or "")[:200],
            "kind": kind,
            "stacks": tag(text, CFG["stacks"]),
            "categories": tag(text, CFG["categories"]),
            "stars": stars,
            "weekly_stars": round(weekly, 1),
            "growth_measured": measured,
            "pushed_days_ago": pushed,
            "license": (r.get("license") or {}).get("spdx_id"),
            "official": official,
            "score": round(score, 2),
            "install": install_hint(r, kind),
        })
    out.sort(key=lambda e: e["score"], reverse=True)
    return out


def main():
    prev = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    if "--fixture" in sys.argv:
        repos = json.load(open(sys.argv[sys.argv.index("--fixture") + 1], encoding="utf-8"))
    else:
        repos = fetch_all()
    entries = build(repos, prev)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"generated_at": NOW.isoformat().replace("+00:00", "Z"),
               "count": len(entries), "entries": entries},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"index: {len(entries)} entries → {OUT}")


if __name__ == "__main__":
    main()
