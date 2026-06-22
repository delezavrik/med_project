from __future__ import annotations

import csv
import json
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path.cwd()

EXCLUDE_DIRS = {
    ".git", ".venv", "__pycache__", ".ipynb_checkpoints",
    "node_modules", "storage/postgres_data", "storage/qdrant_storage",
    "service/storage/postgres_data", "service/storage/qdrant_storage",
}

DATA_EXTS = {".csv", ".parquet", ".jsonl", ".json"}


def is_excluded(path: Path) -> bool:
    s = str(path)
    return any(part in s for part in EXCLUDE_DIRS)


def human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def run_cmd(cmd: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return p.returncode, (p.stdout + p.stderr).strip()
    except Exception as e:
        return 1, str(e)


def inspect_csv(path: Path) -> dict:
    info = {"type": "csv", "rows": None, "columns": [], "error": None}
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
            except Exception:
                dialect = csv.excel

            reader = csv.reader(f, dialect)
            header = next(reader, [])
            info["columns"] = header

            rows = 0
            for _ in reader:
                rows += 1
            info["rows"] = rows
    except Exception as e:
        info["error"] = str(e)
    return info


def inspect_parquet(path: Path) -> dict:
    info = {"type": "parquet", "rows": None, "columns": [], "error": None}
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        info["rows"] = len(df)
        info["columns"] = list(df.columns)
    except Exception as e:
        info["error"] = str(e)
    return info


def inspect_jsonl(path: Path) -> dict:
    info = {"type": "jsonl", "rows": None, "columns": [], "error": None}
    try:
        keys = set()
        rows = 0
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows += 1
                if rows <= 100:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        keys.update(obj.keys())
        info["rows"] = rows
        info["columns"] = sorted(keys)
    except Exception as e:
        info["error"] = str(e)
    return info


def score_columns(columns: list[str]) -> int:
    text_markers = ["text", "review", "отзыв", "feedback", "comment"]
    label_markers = ["label", "labels", "predicted", "class", "метк"]
    score = 0
    cols = [c.lower() for c in columns]
    if any(any(m in c for m in text_markers) for c in cols):
        score += 5
    if any(any(m in c for m in label_markers) for c in cols):
        score += 5
    if any("date" in c or "дата" in c for c in cols):
        score += 2
    if any("product" in c or "товар" in c for c in cols):
        score += 2
    return score


def find_files() -> list[dict]:
    results = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if is_excluded(path):
            continue
        if path.suffix.lower() not in DATA_EXTS:
            continue

        stat = path.stat()
        if path.suffix.lower() == ".csv":
            info = inspect_csv(path)
        elif path.suffix.lower() == ".parquet":
            info = inspect_parquet(path)
        elif path.suffix.lower() == ".jsonl":
            info = inspect_jsonl(path)
        else:
            info = {"type": "json", "rows": None, "columns": [], "error": None}

        info["path"] = str(path)
        info["size"] = human_size(stat.st_size)
        info["score"] = score_columns(info.get("columns") or [])
        results.append(info)

    return sorted(results, key=lambda x: (x["score"], x.get("rows") or 0), reverse=True)


def check_postgres() -> str:
    compose = ROOT / "service" / "docker-compose.dev.yml"
    if not compose.exists():
        return "service/docker-compose.dev.yml не найден"

    cmds = [
        ["docker", "compose", "-f", str(compose), "exec", "-T", "postgres",
         "psql", "-U", "reviews_user", "-d", "reviews_db", "-c", "\\dt"],
        ["docker", "compose", "-f", str(compose), "exec", "-T", "postgres",
         "psql", "-U", "reviews_user", "-d", "reviews_db", "-c",
         "SELECT COUNT(*) AS total_reviews, COUNT(review_date) AS with_date, COUNT(*) - COUNT(review_date) AS without_date, MIN(review_date) AS min_date, MAX(review_date) AS max_date FROM reviews;"],
        ["docker", "compose", "-f", str(compose), "exec", "-T", "postgres",
         "psql", "-U", "reviews_user", "-d", "reviews_db", "-c",
         "SELECT label, COUNT(DISTINCT review_id) AS review_count FROM review_labels GROUP BY label ORDER BY review_count DESC LIMIT 30;"],
        ["docker", "compose", "-f", str(compose), "exec", "-T", "postgres",
         "psql", "-U", "reviews_user", "-d", "reviews_db", "-c",
         "SELECT review_id, review_date, LEFT(text, 120) AS text_preview, product_id, product_name, category, brand, rating FROM reviews LIMIT 10;"],
    ]

    out = []
    for cmd in cmds:
        code, text = run_cmd(cmd)
        out.append("$ " + " ".join(cmd))
        out.append(text)
        out.append("")
    return "\n".join(out)


def check_qdrant() -> str:
    try:
        with urllib.request.urlopen("http://localhost:6333/collections", timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return f"Qdrant localhost:6333 недоступен: {e}"

    out = ["Qdrant collections:", json.dumps(data, ensure_ascii=False, indent=2)]

    collections = data.get("result", {}).get("collections", [])
    for c in collections:
        name = c.get("name")
        if not name:
            continue
        try:
            with urllib.request.urlopen(f"http://localhost:6333/collections/{name}", timeout=5) as r:
                detail = json.loads(r.read().decode("utf-8"))
            out.append(f"\nCollection detail: {name}")
            out.append(json.dumps(detail, ensure_ascii=False, indent=2))
        except Exception as e:
            out.append(f"\nНе удалось прочитать collection {name}: {e}")

    return "\n".join(out)


def main():
    report = []
    report.append("# DATA LOCATIONS REPORT\n")

    report.append("## 1. Candidate data files\n")
    files = find_files()
    for x in files[:50]:
        report.append(f"### {x['path']}")
        report.append(f"- type: {x['type']}")
        report.append(f"- size: {x['size']}")
        report.append(f"- rows: {x.get('rows')}")
        report.append(f"- score: {x.get('score')}")
        report.append(f"- columns: {x.get('columns')[:30]}")
        if x.get("error"):
            report.append(f"- error: {x['error']}")
        report.append("")

    report.append("\n## 2. PostgreSQL service database\n")
    report.append("```text")
    report.append(check_postgres())
    report.append("```")

    report.append("\n## 3. Qdrant\n")
    report.append("```json")
    report.append(check_qdrant())
    report.append("```")

    out_path = ROOT / "data_locations_report.md"
    out_path.write_text("\n".join(report), encoding="utf-8")
    print(f"Готово: {out_path}")


if __name__ == "__main__":
    main()
