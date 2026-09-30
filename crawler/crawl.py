#!/usr/bin/env python3
"""
트렌드 인덱스 생성기.

1) GitHub 검색으로 후보 수집
2) 1차 점수로 상위 N개만 추려서 상세 조사 (API 한도 절약)
   - git tree  → 실제 구성 확인 (marketplace.json / plugin.json / SKILL.md / MCP / hooks)
                 → 정확한 설치 명령 생성, 진짜 스킬/플러그인 아니면 제외
   - stargazers → 최근 7일 스타 수 실측 (첫 실행부터 트렌드 반영)
3) 스택/카테고리 태깅 (설명 + topics + 주 언어 + 스킬/플러그인 폴더명)
4) index/index.json 저장

환경변수: GITHUB_TOKEN (Actions 에선 자동 제공)
사용: python crawler/crawl.py [--fixture dir]   # fixture = 오프라인 테스트용 응답 폴더
"""
import json, math, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, "crawler", "stacks.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "index", "index.json")
NOW = datetime.now(timezone.utc)

MIN_STARS = 20           # 노이즈 컷
STALE_DAYS = 120         # 이 기간 커밋 없으면 제외
PER_QUERY_PAGES = 3      # 쿼리당 100 x 3
ENRICH_TOP = 150         # 상세 조사 대상 수 (API 한도: GITHUB_TOKEN 1000req/h)
STAR_PAGES_MAX = 3       # 최근 스타 집계 시 뒤에서부터 볼 페이지 수 (100개/페이지)

FIXTURE = sys.argv[sys.argv.index("--fixture") + 1] if "--fixture" in sys.argv else None


class RateLimited(Exception):
    pass


def api(path, params=None, accept="application/vnd.github+json"):
    """GitHub API GET. (json, headers) 반환. fixture 모드면 파일에서 읽음."""
    if FIXTURE:
        key = (path.strip("/").replace("/", "__") + ("__" + urllib.parse.urlencode(params) if params else ""))
        fp = os.path.join(FIXTURE, key + ".json")
        if not os.path.exists(fp):
            raise urllib.error.HTTPError(path, 404, "fixture missing", {}, None)
        d = json.load(open(fp, encoding="utf-8"))
        return d.get("body"), d.get("headers", {})
    url = "https://api.github.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": "agentkit-crawler",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"} if os.environ.get("GITHUB_TOKEN") else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and e.headers.get("X-RateLimit-Remaining") == "0":
            raise RateLimited()
        raise


# ---------------------------------------------------------------- 1. 수집
def fetch_candidates():
    seen = {}
    for q in CFG["queries"]:
        for p in range(1, PER_QUERY_PAGES + 1):
            try:
                body, _ = api("/search/repositories", {"q": f"{q} stars:>={MIN_STARS}", "sort": "updated",
                                                        "order": "desc", "per_page": 100, "page": p})
            except Exception as e:
                print(f"[warn] search {q} p{p}: {e}", file=sys.stderr)
                break
            items = body.get("items", [])
            for it in items:
                seen[it["full_name"]] = it
            if len(items) < 100:
                break
            if not FIXTURE:
                time.sleep(2.5)  # search API: 30 req/min
    return list(seen.values())


def days_since(iso):
    return max((NOW - datetime.fromisoformat(iso.replace("Z", "+00:00"))).days, 0)


# ---------------------------------------------------------------- 2. 상세 조사
def inspect_tree(r):
    """레포 파일 구조로 실제 종류/설치 방법 판별."""
    body, _ = api(f"/repos/{r['full_name']}/git/trees/{r['default_branch']}", {"recursive": "1"})
    paths = [t["path"] for t in body.get("tree", []) if t.get("type") == "blob"]
    low = [p.lower() for p in paths]
    info = {"skills": [], "plugins": [], "marketplace": None, "has_hooks": False, "has_mcp": False,
            "has_scripts": False}

    # 플러그인 마켓플레이스
    if ".claude-plugin/marketplace.json" in low:
        try:
            m, _ = api(f"/repos/{r['full_name']}/contents/.claude-plugin/marketplace.json",
                       accept="application/vnd.github.raw+json")
            if isinstance(m, dict):
                info["marketplace"] = m.get("name")
                info["plugins"] = [p.get("name") for p in m.get("plugins", []) if p.get("name")][:30]
        except Exception as e:
            print(f"[warn] marketplace {r['full_name']}: {e}", file=sys.stderr)

    for p in low:
        if p.endswith("/skill.md") or p == "skill.md":
            name = p.rsplit("/", 2)[-2] if "/" in p else r["name"]
            info["skills"].append(name)
        if p.endswith("hooks.json") or p.endswith("hooks/hooks.json") or "/hooks/" in p:
            info["has_hooks"] = True
        if p.endswith(".mcp.json") or "mcp-server" in p or p.endswith("mcp.json"):
            info["has_mcp"] = True
        if p.endswith((".sh", ".ps1", ".py", ".js", ".ts")) and ("scripts/" in p or "hooks/" in p):
            info["has_scripts"] = True
    info["skills"] = sorted(set(info["skills"]))[:50]
    return info


def recent_stars(r, days=7):
    """최근 N일 스타 수 실측. stargazers 마지막 페이지부터 역순으로."""
    if r["stargazers_count"] == 0:
        return 0
    last = max(1, math.ceil(r["stargazers_count"] / 100))
    if last > 400:  # GitHub 는 40,000 개 이후 페이지 제공 안 함
        return None
    cutoff = NOW - timedelta(days=days)
    count = 0
    for page in range(last, max(0, last - STAR_PAGES_MAX), -1):
        body, _ = api(f"/repos/{r['full_name']}/stargazers", {"per_page": 100, "page": page},
                      accept="application/vnd.github.star+json")
        if not body:
            continue
        stamps = [datetime.fromisoformat(s["starred_at"].replace("Z", "+00:00")) for s in body if s.get("starred_at")]
        count += sum(1 for t in stamps if t >= cutoff)
        if stamps and min(stamps) < cutoff:
            return count  # 이 페이지에서 7일 경계 넘음 → 정확
    return count  # 페이지 한도까지 전부 최근 → 하한값


def install_cmds(r, info):
    name = r["full_name"]
    cmds = []
    if info["marketplace"]:
        cmds.append(f"/plugin marketplace add {name}")
        for p in info["plugins"][:5]:
            cmds.append(f"/plugin install {p}@{info['marketplace']}")
    elif info["skills"]:
        if len(info["skills"]) == 1:
            cmds.append(f"npx skills add {name}")
        else:
            cmds.append(f"npx skills add {name} --skill <{'|'.join(info['skills'][:5])}>")
    elif info["has_mcp"]:
        cmds.append(f"# MCP 서버: README 설치법 확인 https://github.com/{name}")
    return cmds


def kind_of(info):
    if info["marketplace"]:
        return "plugin"
    if info["skills"]:
        return "skill"
    if info["has_mcp"]:
        return "mcp"
    return None


# ---------------------------------------------------------------- 3. 태깅
def tag(text, tokens, table):
    hits = []
    for key, kws in table.items():
        for kw in kws:
            # 짧은 키워드(ts, go, ui 등)는 토큰 일치만, 긴 건 부분일치
            if (len(kw) <= 3 and kw in tokens) or (len(kw) > 3 and kw in text):
                hits.append(key)
                break
    return hits


def tags_for(r, info):
    parts = [r["name"], r.get("description") or "", " ".join(r.get("topics", [])),
             " ".join(info["skills"]), " ".join(info["plugins"])]
    text = " ".join(parts).lower()
    tokens = set(text.replace("/", " ").replace("_", " ").replace("-", " ").split()) | set(text.split())
    # 레포 주 언어는 스킬의 '구현 언어'라 스택 판단에 안 씀 (오태깅 원인)
    stacks = tag(text, tokens, CFG["stacks"])
    cats = tag(text, tokens, CFG["categories"])
    return stacks, cats


# ---------------------------------------------------------------- 4. 점수
def score(stars, weekly, pushed, official):
    return round(math.log1p(max(weekly, 0)) * 3      # 성장 속도 (메인)
                 + math.log1p(stars) * 0.5            # 규모 (보조)
                 + math.exp(-pushed / 30) * 2         # 활발함
                 + (3 if official else 0), 2)         # 공식 가산점


def build(repos, prev):
    prev_map = {e["repo"]: e for e in prev.get("entries", [])}
    prev_at = prev.get("generated_at")
    gap = days_since(prev_at) if prev_at else None

    # 1차 필터 + 1차 점수 (근사 성장률)
    cands = []
    for r in repos:
        if r.get("archived") or r.get("fork"):
            continue
        pushed = days_since(r["pushed_at"])
        if pushed > STALE_DAYS:
            continue
        age = max(days_since(r["created_at"]), 1)
        approx = r["stargazers_count"] * 7 / age
        official = r["owner"]["login"] in CFG["official_owners"]
        cands.append((score(r["stargazers_count"], approx, pushed, official), r, pushed, approx, official))
    cands.sort(key=lambda x: x[0], reverse=True)

    out, limited = [], False
    for _, r, pushed, approx, official in cands[:ENRICH_TOP]:
        info = None
        weekly, method = approx, "estimate"
        if not limited:
            try:
                info = inspect_tree(r)
                rs = recent_stars(r)
                if rs is not None:
                    weekly, method = rs, "stargazers"
            except RateLimited:
                limited = True
                print("[warn] rate limit 도달 → 나머지는 근사치/기본값", file=sys.stderr)
            except Exception as e:
                print(f"[warn] enrich {r['full_name']}: {e}", file=sys.stderr)
        p = prev_map.get(r["full_name"])
        if method == "estimate" and p and gap:
            weekly, method = (r["stargazers_count"] - p["stars"]) * 7 / gap, "snapshot"
        if info is None:  # 상세조사 실패 → 이전 인덱스 정보 재사용
            if p:
                info = p.get("_info") or {}
            else:
                continue
        kind = kind_of(info) if "skills" in info else p.get("kind")
        if not kind:
            continue  # 진짜 스킬/플러그인/MCP 아님 → 제외
        stacks, cats = tags_for(r, {**{"skills": [], "plugins": []}, **info})
        out.append({
            "repo": r["full_name"],
            "url": r["html_url"],
            "description": (r.get("description") or "")[:200],
            "kind": kind,
            "stacks": stacks,
            "categories": cats,
            "skills": info.get("skills", [])[:10],
            "plugins": info.get("plugins", [])[:10],
            "stars": r["stargazers_count"],
            "weekly_stars": round(weekly, 1),
            "growth_method": method,          # stargazers(실측) | snapshot(주간 비교) | estimate(추정)
            "pushed_days_ago": pushed,
            "created_days_ago": days_since(r["created_at"]),
            "license": (r.get("license") or {}).get("spdx_id"),
            "official": official,
            "risk": {"hooks": info.get("has_hooks", False), "scripts": info.get("has_scripts", False),
                     "no_license": not (r.get("license") or {}).get("spdx_id"),
                     "new_repo": days_since(r["created_at"]) < 30},
            "install": install_cmds(r, info) if "skills" in info else p.get("install", []),
            "score": score(r["stargazers_count"], weekly, pushed, official),
            "_info": info,
        })
    out.sort(key=lambda e: e["score"], reverse=True)
    return out


def main():
    prev = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    entries = build(fetch_candidates(), prev)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"generated_at": NOW.isoformat().replace("+00:00", "Z"),
               "count": len(entries), "entries": entries},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"index: {len(entries)} entries -> {OUT}")


if __name__ == "__main__":
    main()
