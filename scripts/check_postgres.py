from __future__ import annotations

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://reviews_user:reviews_password@localhost:5432/reviews_db")

with psycopg2.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM reviews;")
        print("reviews:", cur.fetchone()[0])

        cur.execute("""
            SELECT predicted_labels_str, COUNT(*)
            FROM reviews
            GROUP BY predicted_labels_str
            ORDER BY COUNT(*) DESC
            LIMIT 10;
        """)
        print("\nTop label combinations:")
        for row in cur.fetchall():
            print(row)

        cur.execute("""
            SELECT review_id, left(review_text, 160), predicted_labels_str
            FROM reviews
            ORDER BY review_id
            LIMIT 5;
        """)
        print("\nExamples:")
        for row in cur.fetchall():
            print(row)
