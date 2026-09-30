#!/usr/bin/env python3
"""설치 기록 관리: <project>/.claude/stack-setup.lock.json
사용:
  lock.py add --repo owner/name --kind plugin|skill|mcp --scope project|user [--cmd "..."] [--project DIR]
  lock.py remove --repo owner/name [--project DIR]
  lock.py list [--project DIR]
"""
import argparse, json, os, sys
from datetime import datetime, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ap = argparse.ArgumentParser()
ap.add_argument("action", choices=["add", "remove", "list"])
ap.add_argument("--repo")
ap.add_argument("--kind")
ap.add_argument("--scope", default="project")
ap.add_argument("--cmd", default="")
ap.add_argument("--project", default=".")
a = ap.parse_args()

path = os.path.join(a.project, ".claude", "stack-setup.lock.json")
data = []
if os.path.exists(path):
    try:
        data = json.load(open(path, encoding="utf-8"))
    except ValueError:
        data = []

if a.action in ("add", "remove") and not a.repo:
    sys.exit("--repo 필요")
data = [e for e in data if e.get("repo", "").lower() != (a.repo or "").lower()] if a.action != "list" else data
if a.action == "add":
    data.append({"repo": a.repo, "kind": a.kind, "scope": a.scope, "cmd": a.cmd,
                 "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
if a.action != "list":
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(data, ensure_ascii=False, indent=1))
