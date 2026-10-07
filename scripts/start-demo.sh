#!/bin/sh
set -eu
D1ENV_PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$D1ENV_PROJECT_DIR"
if ! command -v uv >/dev/null 2>&1; then
  echo "源码开发入口需要 uv；便携发行包使用随包运行时，Ubuntu 安装验收见阶段报告。" >&2
  exit 1
fi
if [ ! -f frontend/dist/index.html ]; then
  echo "请先按 README 构建前端：cd frontend && npm ci && npm run build" >&2
  exit 1
fi
export UV_PYTHON_INSTALL_DIR="$D1ENV_PROJECT_DIR/work/python"
export UV_PROJECT_ENVIRONMENT="$D1ENV_PROJECT_DIR/work/venv310"
export D1ENV_STATE_DIR="${D1ENV_STATE_DIR:-$D1ENV_PROJECT_DIR/work/state}"
exec uv run --locked --python 3.10 d1env ui --demo "$@"
