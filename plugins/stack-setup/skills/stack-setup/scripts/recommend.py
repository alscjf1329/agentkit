#!/usr/bin/env python3
"""
트렌드 인덱스에서 스택 맞춤 추천.
사용: recommend.py --stacks spring,oracle [--top 3] [--index URL|PATH] [--installed a/b,c/d] [--project DIR]

- 스택 매칭 항목 우선, 부족하면 범용(스택 태그 없음) 항목으로 채움
- 카테고리별 top N (보여주고 카테고리당 1개 고르게)
- 이미 설치된 것 제외: --installed + <project>/.claude/stack-setup.lock.json 자동 반영
- 인덱스가 오래됐으면 stale=true
"""
import argparse, json, os, sys, urllib.request
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔(cp949) 깨짐 방지
except Exception:
    pass

DEFAULT_INDEX = os.environ.get(
    "AGENTKIT_INDEX_URL",
    "https://raw.githubusercontent.com/alscjf1329/agentkit/main/index/index.json")
HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_FALLBACK = os.path.join(HERE, "..", "data", "index.json")  # 플러그인에 번들된 사본
STALE_DAYS = 21


def load(src):
    try:
        if src.startswith("http"):
            with urllib.request.urlopen(src, timeout=15) as r:
                return json.load(r), "remote"
        if os.path.exists(src):
            return json.load(open(src, encoding="utf-8")), "file"
    except Exception as e:
        print(f"[warn] index load 실패 ({e}) -> 번들 사본 사용", file=sys.stderr)
    return json.load(open(LOCAL_FALLBACK, encoding="utf-8")), "bundled"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stacks", default="")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--index", default=DEFAULT_INDEX)
    ap.add_argument("--installed", default="")
    ap.add_argument("--project", default=".")
    a = ap.parse_args()

    idx, source = load(a.index)
    want = {s.strip().lower() for s in a.stacks.split(",") if s.strip()}
    installed = {s.strip().lower() for s in a.installed.split(",") if s.strip()}
    lock = os.path.join(a.project, ".claude", "stack-setup.lock.json")
    if os.path.exists(lock):
        try:
            installed |= {e["repo"].lower() for e in json.load(open(lock, encoding="utf-8"))}
        except Exception:
            pass

    entries = [e for e in idx.get("entries", []) if e["repo"].lower() not in installed]

    def rank(e):
        return (len(want & set(e["stacks"])), e["score"])

    by_cat, used = {}, set()
    for e in sorted(entries, key=rank, reverse=True):
        match = sorted(want & set(e["stacks"]))
        if not match and e["stacks"]:  # 다른 스택 전용 → 제외
            continue
        for c in (e["categories"] or ["general"]):
            lst = by_cat.setdefault(c, [])
            if len(lst) < a.top and e["repo"] not in used:
                slim = {k: v for k, v in e.items() if not k.startswith("_")}
                lst.append({**slim, "stack_match": match})
                used.add(e["repo"])
                break

    gen = idx.get("generated_at")
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(gen.replace("Z", "+00:00"))).days if gen else None
    print(json.dumps({
        "index_source": source,
        "index_generated_at": gen,
        "index_age_days": age,
        "stale": age is None or age > STALE_DAYS,
        "stacks": sorted(want),
        "excluded_installed": sorted(installed),
        "by_category": by_cat,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
