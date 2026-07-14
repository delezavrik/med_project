"""Pytest configuration: добавляем backend в sys.path, чтобы `from app.*` работало и локально, и в Docker."""

import sys
from pathlib import Path

_here = Path(__file__).resolve().parent
# Local host layout: service/tests → добавляем service/backend
# Docker layout:     /app/tests    → добавляем /app
for candidate in (_here.parent / "backend", _here.parent):
    if (candidate / "app" / "__init__.py").exists() or (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break
