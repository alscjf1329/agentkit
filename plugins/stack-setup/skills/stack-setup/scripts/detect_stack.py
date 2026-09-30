#!/usr/bin/env python3
"""프로젝트 스택 감지 (루트 + 1단계 하위 폴더 — 모노레포 대응).
출력: JSON {"stacks": [...], "evidence": {stack: "파일경로"}, "empty": bool}"""
import json, os, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 윈도우 콘솔(cp949) 깨짐 방지
except Exception:
    pass

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
SKIP = {".git", "node_modules", ".venv", "venv", "build", "dist", "target", ".gradle", ".idea",
        ".next", "out", "bin", "obj", "Library", "Temp", ".claude"}
stacks, ev = set(), {}


def hit(stack, why):
    stacks.add(stack)
    ev.setdefault(stack, why)


def read(d, name):
    try:
        return open(os.path.join(d, name), encoding="utf-8", errors="ignore").read().lower()
    except OSError:
        return None


def scan(d):
    rel = os.path.relpath(d, ROOT)
    at = (lambda f: f if rel == "." else f"{rel}/{f}")

    for f in ("build.gradle", "build.gradle.kts", "pom.xml"):
        t = read(d, f)
        if t is None:
            continue
        hit("java", at(f))
        if "spring" in t: hit("spring", at(f))
        if f.endswith(".kts") or "kotlin" in t: hit("kotlin", at(f))
        if "ojdbc" in t or "oracle" in t: hit("oracle", at(f))
        if "postgresql" in t: hit("postgres", at(f))
        if "mysql" in t or "mariadb" in t: hit("mysql", at(f))

    pkg = read(d, "package.json")
    if pkg is not None:
        try:
            j = json.loads(pkg)
            deps = {**j.get("dependencies", {}), **j.get("devdependencies", {})}
        except ValueError:
            deps = {}
        hit("javascript", at("package.json"))
        if read(d, "tsconfig.json") is not None: hit("typescript", at("tsconfig.json"))
        elif "typescript" in deps: hit("typescript", at("package.json:typescript"))
        for dep, st in (("next", "nextjs"), ("react", "react"), ("@nestjs/core", "nestjs"), ("vue", "vue"),
                        ("nuxt", "vue"), ("pg", "postgres"), ("oracledb", "oracle"), ("mysql2", "mysql"),
                        ("prisma", "prisma"), ("tailwindcss", "tailwind"), ("@playwright/test", "playwright")):
            if dep in deps: hit(st, at(f"package.json:{dep}"))

    for f in ("pyproject.toml", "requirements.txt", "setup.py", "Pipfile"):
        t = read(d, f)
        if t is None:
            continue
        hit("python", at(f))
        for kw, st in (("django", "django"), ("fastapi", "fastapi"), ("flask", "flask")):
            if kw in t: hit(st, at(f))

    for f, st in (("go.mod", "go"), ("Cargo.toml", "rust"), ("pubspec.yaml", "flutter"),
                  ("Package.swift", "swift"), ("Dockerfile", "docker"), ("docker-compose.yml", "docker"),
                  ("compose.yaml", "docker")):
        if read(d, f) is not None: hit(st, at(f))
    if os.path.isdir(os.path.join(d, "ProjectSettings")) and os.path.isdir(os.path.join(d, "Assets")):
        hit("unity", at("ProjectSettings/"))
    try:
        if any(n.endswith((".csproj", ".sln")) for n in os.listdir(d)): hit("csharp", at("*.csproj"))
    except OSError:
        pass


scan(ROOT)
try:
    for n in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, n)
        if os.path.isdir(p) and n not in SKIP and not n.startswith("."):
            scan(p)
except OSError:
    pass

print(json.dumps({"root": ROOT, "stacks": sorted(stacks), "evidence": ev, "empty": not stacks},
                 ensure_ascii=False))
