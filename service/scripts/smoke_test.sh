#!/usr/bin/env bash
set -euo pipefail

curl -s http://localhost:8000/health | python -m json.tool
curl -s http://localhost:8000/api/v1/templates | python -m json.tool

curl -s -X POST http://localhost:8000/api/v1/templates/count_by_problem/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "filters": {
      "date_from": "2025-08-01",
      "date_to": "2025-10-15",
      "labels": ["Доставка/получение"],
      "category": "Книги"
    },
    "add_analytical_summary": false,
    "limit": 20
  }' | python -m json.tool
