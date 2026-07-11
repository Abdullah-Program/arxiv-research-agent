import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

ANALYTICS_DB = Path(__file__).resolve().parent.parent / "data" / "analytics.db"

def get_conn():
    ANALYTICS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ANALYTICS_DB))
    conn.row_factory = sqlite3.Row
    return conn

def init_analytics():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS query_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        grade TEXT,
        hallucination_check TEXT,
        confidence_score REAL,
        docs_found INTEGER,
        retry_count INTEGER DEFAULT 0,
        needs_rag INTEGER DEFAULT 1,
        latency_ms REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def log_query(query: str, grade: str = None, hallucination_check: str = None,
              confidence_score: float = None, docs_found: int = 0,
              retry_count: int = 0, needs_rag: bool = True, latency_ms: float = 0):
    try:
        conn = get_conn()
        conn.execute("""
            INSERT INTO query_events 
            (query, grade, hallucination_check, confidence_score, docs_found, retry_count, needs_rag, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (query, grade, hallucination_check, confidence_score,
              docs_found, retry_count, 1 if needs_rag else 0, latency_ms))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[analytics_db] log error: {e}")

def get_stats():
    conn = get_conn()
    c = conn.cursor()

    # Total queries
    total = c.execute("SELECT COUNT(*) FROM query_events").fetchone()[0]
    
    # Successful retrieval rate (grade=relevant)
    relevant = c.execute("SELECT COUNT(*) FROM query_events WHERE grade='relevant'").fetchone()[0]
    retrieval_rate = round((relevant / total * 100) if total > 0 else 0, 1)

    # Hallucination rate
    hallucinated = c.execute("SELECT COUNT(*) FROM query_events WHERE hallucination_check='hallucinated'").fetchone()[0]
    halu_rate = round((hallucinated / total * 100) if total > 0 else 0, 1)

    # Avg confidence
    avg_conf = c.execute("SELECT AVG(confidence_score) FROM query_events WHERE confidence_score IS NOT NULL").fetchone()[0]
    avg_conf = round((avg_conf or 0) * 100, 1)

    # Avg docs found
    avg_docs = c.execute("SELECT AVG(docs_found) FROM query_events").fetchone()[0]
    avg_docs = round(avg_docs or 0, 1)

    # RAG vs direct
    rag_count    = c.execute("SELECT COUNT(*) FROM query_events WHERE needs_rag=1").fetchone()[0]
    direct_count = c.execute("SELECT COUNT(*) FROM query_events WHERE needs_rag=0").fetchone()[0]

    # Queries per day (last 7 days)
    daily = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = c.execute(
            "SELECT COUNT(*) FROM query_events WHERE DATE(created_at)=?", (day,)
        ).fetchone()[0]
        daily.append({"date": day, "count": count})

    # Top queries (most frequent keywords)
    rows = c.execute("SELECT query FROM query_events ORDER BY id DESC LIMIT 100").fetchall()
    all_words = []
    stopwords = {"the","a","an","is","are","how","what","does","in","of","and","to","for","with","on","at","by"}
    for row in rows:
        words = [w.lower().strip("?.,!") for w in row[0].split() if len(w) > 3 and w.lower() not in stopwords]
        all_words.extend(words)
    top_keywords = [{"keyword": w, "count": c2} for w, c2 in Counter(all_words).most_common(8)]

    # Recent queries
    recent = c.execute(
        "SELECT query, grade, confidence_score, docs_found, created_at FROM query_events ORDER BY id DESC LIMIT 10"
    ).fetchall()

    conn.close()
    return {
        "total_queries":   total,
        "retrieval_rate":  retrieval_rate,
        "hallucination_rate": halu_rate,
        "avg_confidence":  avg_conf,
        "avg_docs":        avg_docs,
        "rag_count":       rag_count,
        "direct_count":    direct_count,
        "daily_queries":   daily,
        "top_keywords":    top_keywords,
        "recent_queries":  [dict(r) for r in recent],
    }

init_analytics()
