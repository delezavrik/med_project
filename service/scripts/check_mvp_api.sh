#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "1) health"
curl -s "$BASE_URL/health" | python -m json.tool

echo "\n2) db stats"
curl -s "$BASE_URL/api/v1/debug/db-stats" | python -m json.tool

echo "\n3) count_by_problem: Упаковка"
curl -s -X POST "$BASE_URL/api/v1/templates/count_by_problem/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "labels": ["Упаковка"]
    },
    "add_analytical_summary": false,
    "limit": 20
  }' | python -m json.tool

echo "\n4) top_problems"
curl -s -X POST "$BASE_URL/api/v1/templates/top_problems/execute" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {},
    "add_analytical_summary": false,
    "limit": 10
  }' | python -m json.tool
