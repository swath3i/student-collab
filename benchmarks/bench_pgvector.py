"""
pgvector benchmark for TeamUp recommendation queries.

Tests three query strategies:
  - brute_force : fetch all embeddings, compute composite score in Python
  - hnsw        : HNSW indexes + candidate merging, rerank composite in Python
  - sequential  : single SQL expression with composite score, sequential scan

Measures: p50/p95/p99 latency, QPS, indexing time, memory, recall@20.

Usage:
    python bench_pgvector.py --scale 1k
    python bench_pgvector.py --scale 10k
    python bench_pgvector.py --scale all
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
import psycopg2
from tqdm import tqdm

# ── Config ─────────────────────────────────────────────────────────────────────
PG_DSN = os.environ.get(
    "PG_DSN",
    "host=localhost port=5432 dbname=student_collab user=postgres password=postgres123"
)
DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
NUM_QUERIES = 100
TOP_K = 20
CANDIDATE_K = 100       # candidates pulled per vector in HNSW mode
SKILL_WEIGHT = 0.35
INTENT_WEIGHT = 0.65


# ── Helpers ────────────────────────────────────────────────────────────────────

def cosine_sim_batch(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Vectorised cosine similarity: query (384,) vs matrix (N, 384)."""
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query)
    norms = np.where(norms == 0, 1e-10, norms)
    return matrix @ query / norms


def load_parquet(scale: str) -> pd.DataFrame:
    path = DATA_DIR / f"synthetic_{scale}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}\n"
            "Run: python generate_synthetic_data.py --scale " + scale
        )
    return pd.read_parquet(path)


def pg_connect():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    return conn


def register_vector_type(conn):
    """Register pgvector type so numpy arrays round-trip correctly."""
    try:
        from pgvector.psycopg2 import register_vector
        register_vector(conn)
    except ImportError:
        pass  # fallback: embeddings handled as lists


def setup_table(conn, table: str, df: pd.DataFrame):
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.execute(f"""
        CREATE TABLE {table} (
            user_id TEXT PRIMARY KEY,
            department TEXT,
            skill_embedding vector(384),
            intent_embedding vector(384)
        )
    """)
    conn.commit()

    def to_pg_vector(v):
        return "[" + ",".join(f"{x:.8f}" for x in v) + "]"

    rows = [
        (row.user_id, row.department,
         to_pg_vector(row.skill_embedding),
         to_pg_vector(row.intent_embedding))
        for row in df.itertuples(index=False)
    ]
    cur.executemany(
        f"INSERT INTO {table} VALUES (%s, %s, %s::vector, %s::vector)",
        rows,
    )
    conn.commit()
    cur.close()


def create_hnsw_indexes(conn, table: str) -> float:
    cur = conn.cursor()
    t0 = time.perf_counter()
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {table}_skill_hnsw
        ON {table} USING hnsw (skill_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    cur.execute(f"""
        CREATE INDEX IF NOT EXISTS {table}_intent_hnsw
        ON {table} USING hnsw (intent_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    conn.commit()
    elapsed = time.perf_counter() - t0
    cur.close()
    return elapsed


def drop_hnsw_indexes(conn, table: str):
    cur = conn.cursor()
    cur.execute(f"DROP INDEX IF EXISTS {table}_skill_hnsw")
    cur.execute(f"DROP INDEX IF EXISTS {table}_intent_hnsw")
    conn.commit()
    cur.close()


def fetch_all_embeddings(conn, table: str, exclude_id: str):
    cur = conn.cursor()
    cur.execute(
        f"SELECT user_id, skill_embedding, intent_embedding FROM {table} WHERE user_id != %s",
        (exclude_id,),
    )
    rows = cur.fetchall()
    cur.close()
    ids = [r[0] for r in rows]
    skills = np.array([[float(x) for x in r[1][1:-1].split(",")] for r in rows])
    intents = np.array([[float(x) for x in r[2][1:-1].split(",")] for r in rows])
    return ids, skills, intents


def query_brute_force(conn, table: str, q_skill: np.ndarray, q_intent: np.ndarray, qid: str) -> list[str]:
    ids, skills, intents = fetch_all_embeddings(conn, table, qid)
    skill_sims = cosine_sim_batch(q_skill, skills)
    intent_sims = cosine_sim_batch(q_intent, intents)
    scores = SKILL_WEIGHT * skill_sims + INTENT_WEIGHT * intent_sims
    top_idx = np.argpartition(scores, -TOP_K)[-TOP_K:]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
    return [ids[i] for i in top_idx]


def query_hnsw(conn, table: str, q_skill: np.ndarray, q_intent: np.ndarray, qid: str) -> list[str]:
    q_skill_str = "[" + ",".join(f"{x:.6f}" for x in q_skill) + "]"
    q_intent_str = "[" + ",".join(f"{x:.6f}" for x in q_intent) + "]"
    cur = conn.cursor()

    cur.execute(f"""
        SELECT user_id, skill_embedding, intent_embedding FROM {table}
        WHERE user_id != %s
        ORDER BY skill_embedding <=> %s::vector
        LIMIT %s
    """, (qid, q_skill_str, CANDIDATE_K))
    skill_rows = cur.fetchall()

    cur.execute(f"""
        SELECT user_id, skill_embedding, intent_embedding FROM {table}
        WHERE user_id != %s
        ORDER BY intent_embedding <=> %s::vector
        LIMIT %s
    """, (qid, q_intent_str, CANDIDATE_K))
    intent_rows = cur.fetchall()
    cur.close()

    # Merge candidates, compute composite score
    candidates = {}
    for uid, se, ie in skill_rows + intent_rows:
        if uid not in candidates:
            se_arr = np.array([float(x) for x in se[1:-1].split(",")])
            ie_arr = np.array([float(x) for x in ie[1:-1].split(",")])
            candidates[uid] = (se_arr, ie_arr)

    scores = {}
    for uid, (se_arr, ie_arr) in candidates.items():
        s_sim = float(np.dot(q_skill, se_arr) / (np.linalg.norm(q_skill) * np.linalg.norm(se_arr) + 1e-10))
        i_sim = float(np.dot(q_intent, ie_arr) / (np.linalg.norm(q_intent) * np.linalg.norm(ie_arr) + 1e-10))
        scores[uid] = SKILL_WEIGHT * s_sim + INTENT_WEIGHT * i_sim

    top = sorted(scores, key=scores.get, reverse=True)[:TOP_K]
    return top


def query_sequential(conn, table: str, q_skill: np.ndarray, q_intent: np.ndarray, qid: str) -> list[str]:
    q_skill_str = "[" + ",".join(f"{x:.6f}" for x in q_skill) + "]"
    q_intent_str = "[" + ",".join(f"{x:.6f}" for x in q_intent) + "]"
    cur = conn.cursor()
    cur.execute(f"SET enable_indexscan = off")
    cur.execute(f"""
        SELECT user_id,
               ({SKILL_WEIGHT} * (1 - (skill_embedding <=> %s::vector)) +
                {INTENT_WEIGHT} * (1 - (intent_embedding <=> %s::vector))) AS score
        FROM {table}
        WHERE user_id != %s
        ORDER BY score DESC
        LIMIT %s
    """, (q_skill_str, q_intent_str, qid, TOP_K))
    rows = cur.fetchall()
    cur.execute("SET enable_indexscan = on")
    conn.commit()
    cur.close()
    return [r[0] for r in rows]


def run_queries(query_fn, query_users: list[dict], label: str) -> dict:
    latencies = []
    for qu in tqdm(query_users, desc=f"  {label}", leave=False):
        t0 = time.perf_counter()
        query_fn(qu["skill"], qu["intent"], qu["id"])
        latencies.append((time.perf_counter() - t0) * 1000)

    latencies.sort()
    return {
        "p50_ms": float(np.percentile(latencies, 50)),
        "p95_ms": float(np.percentile(latencies, 95)),
        "p99_ms": float(np.percentile(latencies, 99)),
        "mean_ms": float(np.mean(latencies)),
        "qps": float(1000 / np.mean(latencies)),
    }


def compute_recall(ground_truth: list[list[str]], approx: list[list[str]]) -> float:
    hits = sum(len(set(gt) & set(ap)) for gt, ap in zip(ground_truth, approx))
    return hits / (len(ground_truth) * TOP_K)


def get_table_memory_mb(conn, table: str) -> float:
    cur = conn.cursor()
    cur.execute(f"SELECT pg_total_relation_size('{table}') / 1048576.0")
    mb = cur.fetchone()[0]
    cur.close()
    return float(mb)


def benchmark_scale(conn, df: pd.DataFrame, scale: str) -> list[dict]:
    table = f"bench_pgvector_{scale}"
    n = len(df)
    print(f"\n── pgvector @ {scale} ({n:,} profiles) ──")

    print("  Loading data into PostgreSQL...")
    setup_table(conn, table, df)

    # Sample query users
    query_df = df.sample(n=NUM_QUERIES, random_state=42)
    query_users = [
        {
            "id": row.user_id,
            "skill": np.array(row.skill_embedding),
            "intent": np.array(row.intent_embedding),
        }
        for row in query_df.itertuples(index=False)
    ]

    results = []

    # ── Brute force (no index) ───────────────────────────────────────────────
    print("  Running brute-force queries (ground truth)...")
    drop_hnsw_indexes(conn, table)
    gt_results = []
    bf_latencies = []
    for qu in tqdm(query_users, desc="  brute_force", leave=False):
        t0 = time.perf_counter()
        top = query_brute_force(conn, table, qu["skill"], qu["intent"], qu["id"])
        bf_latencies.append((time.perf_counter() - t0) * 1000)
        gt_results.append(top)

    bf_latencies.sort()
    mem_mb = get_table_memory_mb(conn, table)
    results.append({
        "backend": "pgvector",
        "scale": n,
        "index_type": "brute_force",
        "indexing_time_seconds": 0.0,
        "memory_usage_mb": mem_mb,
        "query_latency_p50_ms": float(np.percentile(bf_latencies, 50)),
        "query_latency_p95_ms": float(np.percentile(bf_latencies, 95)),
        "query_latency_p99_ms": float(np.percentile(bf_latencies, 99)),
        "throughput_qps": float(1000 / np.mean(bf_latencies)),
        "recall_at_20": 1.0,
        "num_queries": NUM_QUERIES,
    })

    # ── Sequential scan (SQL composite, no index) ───────────────────────────
    print("  Running sequential scan queries...")
    seq_latencies = []
    for qu in tqdm(query_users, desc="  sequential", leave=False):
        t0 = time.perf_counter()
        query_sequential(conn, table, qu["skill"], qu["intent"], qu["id"])
        seq_latencies.append((time.perf_counter() - t0) * 1000)

    seq_latencies.sort()
    results.append({
        "backend": "pgvector",
        "scale": n,
        "index_type": "sequential_scan",
        "indexing_time_seconds": 0.0,
        "memory_usage_mb": mem_mb,
        "query_latency_p50_ms": float(np.percentile(seq_latencies, 50)),
        "query_latency_p95_ms": float(np.percentile(seq_latencies, 95)),
        "query_latency_p99_ms": float(np.percentile(seq_latencies, 99)),
        "throughput_qps": float(1000 / np.mean(seq_latencies)),
        "recall_at_20": 1.0,
        "num_queries": NUM_QUERIES,
    })

    # ── HNSW index ──────────────────────────────────────────────────────────
    print("  Building HNSW indexes...")
    indexing_time = create_hnsw_indexes(conn, table)
    print(f"  HNSW indexing time: {indexing_time:.2f}s")
    mem_with_idx = get_table_memory_mb(conn, table)

    hnsw_results = []
    hnsw_latencies = []
    for qu in tqdm(query_users, desc="  hnsw", leave=False):
        t0 = time.perf_counter()
        top = query_hnsw(conn, table, qu["skill"], qu["intent"], qu["id"])
        hnsw_latencies.append((time.perf_counter() - t0) * 1000)
        hnsw_results.append(top)

    hnsw_latencies.sort()
    recall = compute_recall(gt_results, hnsw_results)
    print(f"  HNSW recall@{TOP_K}: {recall:.4f}")

    results.append({
        "backend": "pgvector",
        "scale": n,
        "index_type": "hnsw",
        "indexing_time_seconds": indexing_time,
        "memory_usage_mb": mem_with_idx,
        "query_latency_p50_ms": float(np.percentile(hnsw_latencies, 50)),
        "query_latency_p95_ms": float(np.percentile(hnsw_latencies, 95)),
        "query_latency_p99_ms": float(np.percentile(hnsw_latencies, 99)),
        "throughput_qps": float(1000 / np.mean(hnsw_latencies)),
        "recall_at_20": recall,
        "num_queries": NUM_QUERIES,
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="pgvector benchmark")
    parser.add_argument("--scale", choices=["1k", "10k", "all"], default="1k")
    parser.add_argument("--pg-dsn", default=None)
    args = parser.parse_args()

    global PG_DSN
    if args.pg_dsn:
        PG_DSN = args.pg_dsn

    scales = {"1k": "1k", "10k": "10k"}
    to_run = list(scales.values()) if args.scale == "all" else [args.scale]

    conn = pg_connect()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    cur.close()

    all_results = []
    for scale in to_run:
        df = load_parquet(scale)
        results = benchmark_scale(conn, df, scale)
        all_results.extend(results)

    conn.close()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "pgvector_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    for r in all_results:
        print(f"  {r['backend']} | {r['scale']:>6} | {r['index_type']:<16} | "
              f"p50={r['query_latency_p50_ms']:6.1f}ms  p99={r['query_latency_p99_ms']:7.1f}ms  "
              f"qps={r['throughput_qps']:6.1f}  recall={r['recall_at_20']:.3f}")


if __name__ == "__main__":
    main()
