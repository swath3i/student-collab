"""
PySpark batch embedding pipeline benchmark for TeamUp.

Compares three embedding generation strategies:
  - sequential      : one /embed call per profile (baseline)
  - batch           : /batch_embed in fixed-size batches, no parallelism
  - spark_local[N]  : PySpark mapPartitions — N partitions run concurrently,
                      each partition calls /batch_embed independently

Key insight: Spark adds DATA parallelism on top of batch efficiency.
  - Batch alone:  3x over sequential (model-level batching)
  - Spark local[4]: splits work across 4 threads, each running batch calls
    → approaches 4x * 3x = 12x theoretical max (limited by ML service)

Usage:
    python bench_spark_pipeline.py --scale 1k
    python bench_spark_pipeline.py --scale 10k
"""

# Must be set before PySpark/JVM initialises
import os, sys
os.environ["SPARK_USER"] = "sparkuser"          # Spark checks this first in getCurrentUserName
os.environ["HADOOP_USER_NAME"] = "sparkuser"
os.environ.setdefault("USER", "sparkuser")
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["JAVA_TOOL_OPTIONS"] = (
    "--add-opens=java.base/java.lang=ALL-UNNAMED "
    "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED "
    "-Duser.name=sparkuser"
)

import argparse
import json
import os
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:8001")

PROFILE_COUNTS = [100, 500, 1000, 5000]
BATCH_SIZE = 32
SPARK_WORKERS = [1, 2, 4]


def load_parquet(scale: str) -> pd.DataFrame:
    path = DATA_DIR / f"synthetic_{scale}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    return pd.read_parquet(path)


# ── Embedding strategies ────────────────────────────────────────────────────

def benchmark_sequential(profiles: list[dict], ml_url: str) -> dict:
    """One HTTP POST to /embed per profile — the naive baseline."""
    t0 = time.perf_counter()
    for p in tqdm(profiles, desc="  sequential", leave=False):
        requests.post(f"{ml_url}/embed", json={"text": p["skills_text"]}, timeout=30)
    elapsed = time.perf_counter() - t0
    return _record("sequential", len(profiles), 1, elapsed)


def benchmark_batch(profiles: list[dict], batch_size: int, ml_url: str) -> dict:
    """Single-threaded batch calls to /batch_embed — no Spark."""
    texts = [p["skills_text"] for p in profiles]
    t0 = time.perf_counter()
    for i in tqdm(range(0, len(texts), batch_size), desc=f"  batch-{batch_size}", leave=False):
        chunk = texts[i:i + batch_size]
        requests.post(f"{ml_url}/batch_embed", json={"texts": chunk}, timeout=60)
    elapsed = time.perf_counter() - t0
    return _record(f"batch_{batch_size}", len(profiles), 1, elapsed)


def benchmark_spark(profiles: list[dict], num_workers: int, batch_size: int, ml_url: str) -> dict:
    """
    PySpark local[N] — splits the profile list into N partitions.
    Each partition independently calls /batch_embed on its slice.
    All N partitions run concurrently on N threads.

    Architecture:
        Driver splits texts → N partitions
        Partition 0 → /batch_embed (32 texts) ─┐
        Partition 1 → /batch_embed (32 texts)  ├─ concurrent
        Partition 2 → /batch_embed (32 texts)  │
        Partition 3 → /batch_embed (32 texts) ─┘
        Driver collects all embeddings
    """
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        print("  PySpark not installed — skipping Spark benchmark")
        return None

    spark = (SparkSession.builder
             .appName("TeamUp-EmbeddingBenchmark")
             .master(f"local[{num_workers}]")
             .config("spark.driver.memory", "2g")
             .config("spark.executor.memory", "2g")
             .config("spark.ui.showConsoleProgress", "false")
             .config("spark.driver.bindAddress", "127.0.0.1")
             .config("spark.driver.host", "127.0.0.1")
             .config("spark.ui.enabled", "false")
             .getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    texts = [p["skills_text"] for p in profiles]

    # Distribute texts across N partitions
    rdd = spark.sparkContext.parallelize(texts, num_workers)

    # Each partition processes its slice independently
    _batch_size = batch_size
    _ml_url = ml_url

    def embed_partition(iterator):
        import requests as req
        partition_texts = list(iterator)
        if not partition_texts:
            return iter([])
        embeddings = []
        for i in range(0, len(partition_texts), _batch_size):
            chunk = partition_texts[i:i + _batch_size]
            r = req.post(f"{_ml_url}/batch_embed", json={"texts": chunk}, timeout=60)
            embeddings.extend(r.json()["embeddings"])
        return iter(embeddings)

    t0 = time.perf_counter()
    result = rdd.mapPartitions(embed_partition).collect()
    elapsed = time.perf_counter() - t0

    spark.stop()

    assert len(result) == len(texts), f"Expected {len(texts)} embeddings, got {len(result)}"
    return _record(f"spark_local_{num_workers}", len(profiles), num_workers, elapsed)


def _record(method: str, n: int, parallelism: int, elapsed: float) -> dict:
    return {
        "method": method,
        "n_profiles": n,
        "parallelism": parallelism,
        "total_time_s": elapsed,
        "throughput_per_s": n / elapsed,
        "ms_per_profile": (elapsed / n) * 1000,
    }


# ── Charts ──────────────────────────────────────────────────────────────────

def plot_results(results: list[dict]):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    methods = ["sequential", f"batch_{BATCH_SIZE}"] + [f"spark_local_{w}" for w in SPARK_WORKERS]
    colors  = ["#e74c3c",    "#f39c12",              "#3498db", "#2980b9", "#1a5276"]
    labels  = ["Sequential", f"Batch (bs={BATCH_SIZE})"] + [f"Spark local[{w}]" for w in SPARK_WORKERS]

    ns = sorted(set(r["n_profiles"] for r in results))

    # ── Chart 1: Throughput vs profile count ────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    for method, color, label in zip(methods, colors, labels):
        xs, ys = [], []
        for n in ns:
            match = next((r for r in results if r["method"] == method and r["n_profiles"] == n), None)
            if match:
                xs.append(n)
                ys.append(match["throughput_per_s"])
        if xs:
            ax.plot(xs, ys, marker="o", color=color, label=label, linewidth=2.5, markersize=8)

    ax.set_xlabel("Number of profiles", fontsize=12)
    ax.set_ylabel("Throughput (profiles / second)", fontsize=12)
    ax.set_title("Embedding Pipeline Throughput: Sequential vs Batch vs Spark", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xticks(ns)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "spark_throughput.png", dpi=150)
    plt.close()

    # ── Chart 2: Speedup over sequential ────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    for method, color, label in zip(methods[1:], colors[1:], labels[1:]):
        xs, ys = [], []
        for n in ns:
            seq = next((r for r in results if r["method"] == "sequential" and r["n_profiles"] == n), None)
            match = next((r for r in results if r["method"] == method and r["n_profiles"] == n), None)
            if seq and match:
                xs.append(n)
                ys.append(seq["total_time_s"] / match["total_time_s"])
        if xs:
            ax.plot(xs, ys, marker="o", color=color, label=label, linewidth=2.5, markersize=8)

    ax.axhline(1.0, color="#e74c3c", linestyle="--", alpha=0.6, label="Sequential baseline (1×)")
    ax.set_xlabel("Number of profiles", fontsize=12)
    ax.set_ylabel("Speedup over sequential (×)", fontsize=12)
    ax.set_title("Speedup: Batch and Spark vs Sequential Baseline", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10)
    ax.set_xticks(ns)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "spark_speedup.png", dpi=150)
    plt.close()

    # ── Chart 3: ms per profile grouped bar at n=1000 ───────────────────────
    n_target = 1000
    bar_data = []
    for method, label in zip(methods, labels):
        match = next((r for r in results if r["method"] == method and r["n_profiles"] == n_target), None)
        if match:
            bar_data.append((label, match["ms_per_profile"]))

    if bar_data:
        fig, ax = plt.subplots(figsize=(9, 5))
        bar_labels, bar_vals = zip(*bar_data)
        bar_colors = colors[:len(bar_labels)]
        bars = ax.bar(bar_labels, bar_vals, color=bar_colors, alpha=0.85, width=0.5)
        for bar, val in zip(bars, bar_vals):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                    f"{val:.1f}ms", ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.set_ylabel("Latency per profile (ms)", fontsize=12)
        ax.set_title(f"Per-Profile Latency at n={n_target:,} Profiles", fontsize=13, fontweight="bold")
        ax.set_ylim(0, max(bar_vals) * 1.2)
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "spark_latency_per_profile.png", dpi=150)
        plt.close()

    print(f"Spark charts saved → {CHARTS_DIR}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Spark embedding pipeline benchmark")
    parser.add_argument("--scale", choices=["1k", "10k"], default="1k")
    parser.add_argument("--ml-url", default=None)
    args = parser.parse_args()

    global ML_SERVICE_URL
    if args.ml_url:
        ML_SERVICE_URL = args.ml_url

    df = load_parquet(args.scale)
    n_total = len(df)
    print(f"Loaded {n_total:,} profiles from synthetic_{args.scale}.parquet")

    # Verify ML service is reachable
    try:
        requests.get(f"{ML_SERVICE_URL}/health", timeout=5)
        print(f"ML service reachable at {ML_SERVICE_URL}")
    except Exception:
        print(f"WARNING: ML service not reachable at {ML_SERVICE_URL} — latencies will include retry time")

    results = []

    for n in PROFILE_COUNTS:
        if n > n_total:
            print(f"Skipping n={n} (only {n_total} profiles available)")
            continue

        sample = df.sample(n=n, random_state=42)
        profiles = sample[["user_id", "skills_text", "intent_text"]].to_dict("records")

        print(f"\n── n={n:,} profiles ──")

        # 1. Sequential baseline
        r = benchmark_sequential(profiles, ML_SERVICE_URL)
        results.append(r)
        print(f"  sequential:       {r['throughput_per_s']:>7.1f} profiles/s  ({r['total_time_s']:.2f}s)")

        # 2. Batch without Spark
        r = benchmark_batch(profiles, BATCH_SIZE, ML_SERVICE_URL)
        results.append(r)
        speedup = results[-2]["total_time_s"] / r["total_time_s"]
        print(f"  batch (bs={BATCH_SIZE}):    {r['throughput_per_s']:>7.1f} profiles/s  ({r['total_time_s']:.2f}s)  {speedup:.1f}× speedup")

        # 3. Spark with varying parallelism
        for workers in SPARK_WORKERS:
            r = benchmark_spark(profiles, workers, BATCH_SIZE, ML_SERVICE_URL)
            if r:
                results.append(r)
                seq_r = next(x for x in results if x["method"] == "sequential" and x["n_profiles"] == n)
                speedup = seq_r["total_time_s"] / r["total_time_s"]
                print(f"  spark local[{workers}]:   {r['throughput_per_s']:>7.1f} profiles/s  ({r['total_time_s']:.2f}s)  {speedup:.1f}× speedup")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "spark_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    plot_results(results)

    # Summary table
    print(f"\n{'Method':<22} {'n':>6} {'Workers':>8} {'Profiles/s':>12} {'ms/profile':>12} {'Speedup':>9}")
    print("─" * 75)
    for n in PROFILE_COUNTS:
        seq_r = next((r for r in results if r["method"] == "sequential" and r["n_profiles"] == n), None)
        for r in [x for x in results if x["n_profiles"] == n]:
            speedup = (seq_r["total_time_s"] / r["total_time_s"]) if seq_r else 1.0
            print(f"  {r['method']:<20} {r['n_profiles']:>6} {r['parallelism']:>8} "
                  f"{r['throughput_per_s']:>11.1f} {r['ms_per_profile']:>11.1f}ms "
                  f"{speedup:>8.2f}×")
        print()


if __name__ == "__main__":
    main()
