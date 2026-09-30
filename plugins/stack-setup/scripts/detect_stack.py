#!/usr/bin/env python3
"""프로젝트 디렉토리에서 스택 감지. 출력: JSON {"stacks": [...], "evidence": {...}}"""
import json, os, sys

root = sys.argv[1] if len(sys.argv) > 1 else "."
stacks, ev = set(), {}


def read(p):
    try:
        return open(os.path.join(root, p), encoding="utf-8", errors="ignore").read().lower()
    except OSError:
        return None


def hit(stack, why):
    stacks.add(stack); ev.setdefault(stack, why)


# JVM
for f in ("build.gradle", "build.gradle.kts", "pom.xml"):
    t = read(f)
    if t is None:
        continue
    hit("java", f)
    if "spring" in t: hit("spring", f)
    if f.endswith(".kts") or "kotlin" in t: hit("kotlin", f)
    if "ojdbc" in t or "oracle" in t: hit("oracle", f)
    if "postgresql" in t: hit("postgres", f)

# Node
pkg = read("package.json")
if pkg is not None:
    try:
        d = json.loads(pkg)
        deps = {**d.get("dependencies", {}), **d.get("devdependencies", {})}
    except ValueError:
        deps = {}
    hit("javascript", "package.json")
    if "typescript" in deps or read("tsconfig.json") is not None: hit("typescript", "tsconfig/package.json")
    for dep, st in (("next", "nextjs"), ("react", "react"), ("@nestjs/core", "nestjs"),
                    ("vue", "vue"), ("nuxt", "vue"), ("pg", "postgres"), ("oracledb", "oracle")):
        if dep in deps: hit(st, f"package.json:{dep}")

# Python
for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
    t = read(f)
    if t is None:
        continue
    hit("python", f)
    if "django" in t: hit("django", f)
    if "fastapi" in t: hit("fastapi", f)

# 기타
if read("go.mod") is not None: hit("go", "go.mod")
if read("Cargo.toml") is not None: hit("rust", "Cargo.toml")
if read("pubspec.yaml") is not None: hit("flutter", "pubspec.yaml")
if read("Package.swift") is not None: hit("swift", "Package.swift")
if os.path.isdir(os.path.join(root, "ProjectSettings")) and os.path.isdir(os.path.join(root, "Assets")):
    hit("unity", "ProjectSettings/")
if read("Dockerfile") is not None or read("docker-compose.yml") is not None: hit("docker", "Dockerfile")

print(json.dumps({"stacks": sorted(stacks), "evidence": ev}, ensure_ascii=False))
