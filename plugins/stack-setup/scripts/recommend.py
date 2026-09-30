#!/usr/bin/env python3
"""
트렌드 인덱스에서 스택 맞춤 추천.
사용: recommend.py --stacks spring,oracle [--top 3] [--index URL|PATH] [--installed a/b,c/d]

규칙
- 스택 매칭 항목 우선, 없으면 범용(스택 태그 없음) 항목으로 채움
- 카테고리별 top N  (카테고리당 여러 개 깔면 중복/토큰 낭비라 기본 3개 보여주고 1개 고르게)
- 이미 설치된 것(--installed) 제외
"""
import argparse, json, os, sys, urllib.request

DEFAULT_INDEX = os.environ.get(
    "AI_SETUP_INDEX_URL",
    "https://raw.githubusercontent.com/alscjf1329/ai-stack-setup/main/index/index.json")
# 플러그인 설치 시 plugin 폴더만 복사되므로 번들 사본을 fallback 으로 사용
LOCAL_FALLBACK = os.path.join(os.path.dirname(__file__), "..", "data", "index.json")


def load(src):
    try:
        if src.startswith("http"):
            with urllib.request.urlopen(src, timeout=15) as r:
                return json.load(r)
        if os.path.exists(src):
            return json.load(open(src, encoding="utf-8"))
    except Exception as e:
        print(f"[warn] index load 실패 ({e}) → 로컬 fallback", file=sys.stderr)
    return json.load(open(LOCAL_FALLBACK, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stacks", default="")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--index", default=DEFAULT_INDEX)
    ap.add_argument("--installed", default="")
    a = ap.parse_args()

    idx = load(a.index)
    want = {s.strip() for s in a.stacks.split(",") if s.strip()}
    installed = {s.strip().lower() for s in a.installed.split(",") if s.strip()}
    entries = [e for e in idx["entries"] if e["repo"].lower() not in installed]

    def rank(e):
        match = len(want & set(e["stacks"]))
        return (match, e["score"])

    by_cat, used = {}, set()
    for e in sorted(entries, key=rank, reverse=True):
        stack_ok = (want & set(e["stacks"])) or not e["stacks"]   # 매칭 or 범용
        if not stack_ok:
            continue
        for c in (e["categories"] or ["general"]):
            lst = by_cat.setdefault(c, [])
            if len(lst) < a.top and e["repo"] not in used:
                lst.append({**e, "stack_match": sorted(want & set(e["stacks"]))})
                used.add(e["repo"])
                break

    print(json.dumps({"index_generated_at": idx.get("generated_at"),
                      "stacks": sorted(want), "by_category": by_cat},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
