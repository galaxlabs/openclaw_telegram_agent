#!/usr/bin/env bash
set -euo pipefail

OGH_DIR="${1:-/home/fg/ogh}"

echo "[ogh] inspection started"
echo "  dir: ${OGH_DIR}"

if [[ ! -d "${OGH_DIR}" ]]; then
  echo "[ogh] directory not found"
  exit 1
fi

cd "${OGH_DIR}"

echo
echo "--- pwd ---"
pwd

echo
echo "--- top level ---"
ls -la

echo
echo "--- git ---"
if [[ -d .git ]]; then
  git remote -v || true
  git status --short || true
else
  echo "not a git repo"
fi

echo
echo "--- stack markers ---"
for f in package.json pnpm-lock.yaml package-lock.json yarn.lock bun.lockb \
         requirements.txt pyproject.toml Pipfile poetry.lock \
         docker-compose.yml docker-compose.yaml Dockerfile \
         vercel.json next.config.js next.config.mjs next.config.ts \
         manage.py composer.json ; do
  if [[ -f "${f}" ]]; then
    echo "found: ${f}"
  fi
done

echo
echo "--- likely api routes ---"
find . -maxdepth 4 -type f \( \
  -path "*/api/*" -o \
  -name "route.ts" -o \
  -name "route.js" -o \
  -name "*.py" \
\) | sort | head -n 200

echo
echo "--- package.json scripts ---"
if [[ -f package.json ]]; then
  python3 - <<'PY'
import json
with open("package.json", "r", encoding="utf-8") as f:
    data = json.load(f)
scripts = data.get("scripts", {})
for key, value in scripts.items():
    print(f"{key}: {value}")
PY
fi

echo
echo "--- python deps preview ---"
if [[ -f requirements.txt ]]; then
  sed -n '1,120p' requirements.txt
fi

if [[ -f pyproject.toml ]]; then
  sed -n '1,160p' pyproject.toml
fi

echo
echo "--- vercel config ---"
if [[ -f vercel.json ]]; then
  sed -n '1,200p' vercel.json
fi

echo
echo "--- env examples ---"
find . -maxdepth 3 -type f \( -name ".env*" -o -name "*.example" \) | sort | head -n 100

echo
echo "--- listeners ---"
if command -v ss >/dev/null 2>&1; then
  ss -ltnp || true
fi

echo
echo "--- systemd hints ---"
if command -v systemctl >/dev/null 2>&1; then
  systemctl list-units --type=service --all | grep -Ei 'ogh|node|python|gunicorn|uvicorn|pm2|next|vercel' || true
fi

echo
echo "[ogh] inspection complete"
