"""
Redis caching strategy benchmark for TeamUp recommendations.

Simulates a workload of N users requesting recommendations over a time period.
For each TTL value tests:
  - Cache hit rate
  - Average response time (hit vs miss)
  - Recommendation staleness (Jaccard distance vs fresh results)
  - Effective system load (requests served from cache vs DB)

Uses the synthetic 10k dataset loaded into pgvector as the backing store.
Falls back to 1k if 10k is not available.

Usage:
    python bench_caching.py
    python bench_caching.py --scale 1k
"""

import argparse
import json
import os
import random
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psycopg2
from tqdm import tqdm

PG_DSN = os.environ.get(
    "PG_DSN",
    "host=localhost port=5432 dbname=student_collab user=postgres password=postgres123"
)
DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

TTL_VALUES = [60, 300, 900, 1800, 3600, 21600]   # 1m, 5m, 15m, 30m, 1h, 6h
TTL_LABELS = ["1 min", "5 min", "15 min", "30 min", "1 hour", "6 hours"]

SKILL_WEIGHT = 0.35
INTENT_WEIGHT = 0.65
TOP_K = 20
SIM_DURATION = 3600          # simulated seconds of activity
NUM_ACTIVE_USERS = 200       # users who actively request recommendations
REQUESTS_PER_HOUR = 4        # average requests per user per simulated hour
PROFILE_UPDATE_RATE = 0.01   # fraction of users updating profile per hour
CONNECTION_ACCEPT_RATE = 0.02

# Simulated response times
CACHE_HIT_MS = 2.0           # Redis round-trip
CACHE_MISS_BASE_MS = 50.0    # DB query baseline (overridden by actual measurements if available)


def load_parquet(scale: str) -> pd.DataFrame:
    path = DATA_DIR / f"synthetic_{scale}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_parquet(path)


def pg_connect():
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    return conn


def setup_cache_bench_table(conn, df: pd.DataFrame, table: str):
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.execute(f"""
        CREATE TABLE {table} (
            row_idx INTEGER PRIMARY KEY,
            user_id TEXT,
            skill_embedding vector(384),
            intent_embedding vector(384)
        )
    """)
    conn.commit()

    def to_pg_vector(v):
        return "[" + ",".join(f"{x:.8f}" for x in v) + "]"

    rows = [
        (i, row.user_id,
         to_pg_vector(row.skill_embedding),
         to_pg_vector(row.intent_embedding))
        for i, row in enumerate(df.itertuples(index=False))
    ]
    cur.executemany(
        f"INSERT INTO {table} VALUES (%s, %s, %s::vector, %s::vector)",
        rows,
    )
    conn.commit()

    cur.execute(f"""
        CREATE INDEX {table}_skill_hnsw
        ON {table} USING hnsw (skill_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    cur.execute(f"""
        CREATE INDEX {table}_intent_hnsw
        ON {table} USING hnsw (intent_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)
    conn.commit()
    cur.close()


def compute_recommendations_pg(conn, table: str, q_skill: np.ndarray,
                                q_intent: np.ndarray, qid: str) -> tuple[list[str], float]:
    q_skill_str = "[" + ",".join(f"{x:.6f}" for x in q_skill) + "]"
    q_intent_str = "[" + ",".join(f"{x:.6f}" for x in q_intent) + "]"
    cur = conn.cursor()

    t0 = time.perf_counter()
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
    elapsed_ms = (time.perf_counter() - t0) * 1000
    cur.close()
    return [r[0] for r in rows], elapsed_ms


def jaccard(a: list, b: list) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)


def staleness(cached: list, fresh: list) -> float:
    return 1.0 - jaccard(cached, fresh)


def simulate_workload(
    conn,
    table: str,
    df: pd.DataFrame,
    ttl: int,
    miss_time_ms: float,
) -> dict:
    n = len(df)
    user_ids = df["user_id"].tolist()
    skill_embs = np.array(df["skill_embedding"].tolist(), dtype=np.float32)
    intent_embs = np.array(df["intent_embedding"].tolist(), dtype=np.float32)

    active_idxs = random.sample(range(n), min(NUM_ACTIVE_USERS, n))

    cache: dict[str, dict] = {}

    hits = 0
    misses = 0
    hit_times = []
    miss_times = []
    staleness_scores = []
    invalidations = 0

    request_rate = REQUESTS_PER_HOUR / 3600
    update_rate = PROFILE_UPDATE_RATE / 3600
    connection_rate = CONNECTION_ACCEPT_RATE / 3600

    rng = random.Random(ttl)
    current_time = 0.0

    while current_time < SIM_DURATION:
        dt = rng.expovariate(request_rate * len(active_idxs))
        current_time += dt
        if current_time >= SIM_DURATION:
            break

        uid_idx = rng.choice(active_idxs)
        uid = user_ids[uid_idx]

        if uid in cache and (current_time - cache[uid]["cached_at"]) < ttl:
            hits += 1
            hit_times.append(CACHE_HIT_MS + rng.gauss(0, 0.3))
        else:
            misses += 1
            sim_miss_time = miss_time_ms * rng.uniform(0.8, 1.4)
            miss_times.append(sim_miss_time)

            if uid in cache:
                old_recs = cache[uid]["recs"]
                fresh_recs, _ = compute_recommendations_pg(
                    conn, table, skill_embs[uid_idx], intent_embs[uid_idx], uid
                )
                staleness_scores.append(staleness(old_recs, fresh_recs))
                cache[uid] = {"recs": fresh_recs, "cached_at": current_time}
            else:
                recs, _ = compute_recommendations_pg(
                    conn, table, skill_embs[uid_idx], intent_embs[uid_idx], uid
                )
                cache[uid] = {"recs": recs, "cached_at": current_time}

        # Simulate profile updates → invalidate cache
        if rng.random() < update_rate * dt * len(active_idxs):
            invalidate_idx = rng.choice(active_idxs)
            invalidate_uid = user_ids[invalidate_idx]
            if invalidate_uid in cache:
                del cache[invalidate_uid]
                invalidations += 1

        # Simulate connection accepts → invalidate both users
        if rng.random() < connection_rate * dt * len(active_idxs):
            a, b = rng.sample(active_idxs, 2)
            for idx in [a, b]:
                uid2 = user_ids[idx]
                if uid2 in cache:
                    del cache[uid2]
                    invalidations += 1

    total_requests = hits + misses
    hit_rate = hits / total_requests if total_requests > 0 else 0.0
    avg_response = (
        (hits * np.mean(hit_times) + misses * np.mean(miss_times)) / total_requests
        if total_requests > 0 else 0.0
    )

    return {
        "ttl_seconds": ttl,
        "ttl_label": TTL_LABELS[TTL_VALUES.index(ttl)],
        "total_requests": total_requests,
        "cache_hits": hits,
        "cache_misses": misses,
        "hit_rate": hit_rate,
        "avg_response_ms": avg_response,
        "avg_hit_response_ms": float(np.mean(hit_times)) if hit_times else 0.0,
        "avg_miss_response_ms": float(np.mean(miss_times)) if miss_times else 0.0,
        "avg_staleness": float(np.mean(staleness_scores)) if staleness_scores else 0.0,
        "staleness_p95": float(np.percentile(staleness_scores, 95)) if staleness_scores else 0.0,
        "invalidations": invalidations,
    }


def plot_results(results: list[dict]):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    labels = [r["ttl_label"] for r in results]
    hit_rates = [r["hit_rate"] * 100 for r in results]
    avg_resp = [r["avg_response_ms"] for r in results]
    hit_resp = [r["avg_hit_response_ms"] for r in results]
    miss_resp = [r["avg_miss_response_ms"] for r in results]
    staleness_vals = [r["avg_staleness"] * 100 for r in results]
    db_frac = [(1 - r["hit_rate"]) * 100 for r in results]
    cache_frac = [r["hit_rate"] * 100 for r in results]

    x = np.arange(len(labels))

    # ── Chart 1: Cache hit rate vs TTL ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(labels, hit_rates, marker="o", color="#3498db", linewidth=2.5, markersize=8)
    ax.fill_between(range(len(labels)), hit_rates, alpha=0.15, color="#3498db")
    ax.set_xlabel("Cache TTL", fontsize=12)
    ax.set_ylabel("Cache hit rate (%)", fontsize=12)
    ax.set_title("Cache Hit Rate vs TTL", fontsize=14, fontweight="bold")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "cache_hit_rate.png", dpi=150)
    plt.close()

    # ── Chart 2: Response time vs TTL ───────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, miss_resp, label="Cache miss (DB query)", color="#e74c3c", alpha=0.85)
    ax.bar(x, hit_resp, label="Cache hit (Redis)", color="#2ecc71", alpha=0.85)
    ax.plot(x, avg_resp, marker="D", color="#2c3e50", linewidth=2, label="Weighted average", zorder=5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_xlabel("Cache TTL", fontsize=12)
    ax.set_ylabel("Response time (ms)", fontsize=12)
    ax.set_title("Response Time vs TTL", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "cache_response_time.png", dpi=150)
    plt.close()

    # ── Chart 3: Recommendation staleness vs TTL ─────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(labels, staleness_vals, marker="^", color="#e67e22", linewidth=2.5, markersize=8,
            label="Mean staleness")
    ax.fill_between(range(len(labels)), staleness_vals, alpha=0.15, color="#e67e22")
    ax.set_xlabel("Cache TTL", fontsize=12)
    ax.set_ylabel("Recommendation staleness (%)\n(1 – Jaccard similarity vs fresh)", fontsize=12)
    ax.set_title("Recommendation Staleness vs TTL", fontsize=14, fontweight="bold")
    ax.set_ylim(0, max(staleness_vals) * 1.3 + 1)
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "cache_staleness.png", dpi=150)
    plt.close()

    # ── Chart 4: Load distribution (cache vs DB) ─────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, cache_frac, label="Served from cache", color="#27ae60", alpha=0.85)
    ax.bar(x, db_frac, bottom=cache_frac, label="Hit database", color="#c0392b", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    ax.set_xlabel("Cache TTL", fontsize=12)
    ax.set_ylabel("% of requests", fontsize=12)
    ax.set_title("System Load: Cache vs Database", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "cache_load_distribution.png", dpi=150)
    plt.close()

    print(f"Charts saved → {CHARTS_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Caching strategy benchmark")
    parser.add_argument("--scale", choices=["1k", "10k"], default="10k",
                        help="Dataset scale (default: 10k, falls back to 1k if unavailable)")
    parser.add_argument("--pg-dsn", default=None)
    args = parser.parse_args()

    global PG_DSN
    if args.pg_dsn:
        PG_DSN = args.pg_dsn

    scale = args.scale
    try:
        df = load_parquet(scale)
    except FileNotFoundError:
        print(f"  {scale} dataset not found, falling back to 1k")
        df = load_parquet("1k")
        scale = "1k"

    n = len(df)
    print(f"Using {n:,} profiles for caching benchmark")

    conn = pg_connect()
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    cur.close()

    table = f"bench_cache_{scale}"
    print(f"Loading data into PostgreSQL table {table}...")
    setup_cache_bench_table(conn, df, table)

    # Measure actual DB miss time with a few warm-up queries
    print("Measuring baseline DB query time...")
    sample_df = df.sample(5, random_state=1)
    db_times = []
    for row in sample_df.itertuples(index=False):
        _, t = compute_recommendations_pg(
            conn, table,
            np.array(row.skill_embedding, dtype=np.float32),
            np.array(row.intent_embedding, dtype=np.float32),
            row.user_id,
        )
        db_times.append(t)
    miss_time_ms = float(np.mean(db_times))
    print(f"Baseline DB query time: {miss_time_ms:.1f}ms")

    results = []
    for ttl in TTL_VALUES:
        label = TTL_LABELS[TTL_VALUES.index(ttl)]
        print(f"\nSimulating TTL={label}...")
        r = simulate_workload(conn, table, df, ttl, miss_time_ms)
        results.append(r)
        print(f"  hit_rate={r['hit_rate']:.2%}  avg_resp={r['avg_response_ms']:.1f}ms  "
              f"staleness={r['avg_staleness']:.3f}")

    conn.close()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "caching_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    plot_results(results)


if __name__ == "__main__":
    main()
