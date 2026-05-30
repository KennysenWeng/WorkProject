#!/bin/zsh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  python3 safari_server.py
else
  echo "找不到 python3，請先安裝 Python 3。"
  read "?按 Enter 關閉..."
fi
