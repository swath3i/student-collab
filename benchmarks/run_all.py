"""
Master benchmark runner for TeamUp research extensions.

Runs all experiments across both scales and generates the combined
comparison charts for the thesis.

Usage:
    python run_all.py                    # full run (1k + 10k)
    python run_all.py --scale 1k        # quick validation run
    python run_all.py --skip-data-gen   # if parquet files already exist
    python run_all.py --skip-milvus     # if Milvus is not running
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

RESULTS_DIR = Path(__file__).parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"
HERE = Path(__file__).parent


def run_script(script: str, extra_args: list[str] = None):
    cmd = [sys.executable, str(HERE / script)] + (extra_args or [])
    print(f"\n{'─'*60}")
    print(f"Running: {' '.join(cmd)}")
    print('─'*60)
    t0 = time.time()
    result = subprocess.run(cmd, check=False)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  WARNING: {script} exited with code {result.returncode}")
    else:
        print(f"  Completed in {elapsed:.1f}s")
    return result.returncode == 0


def load_results() -> dict:
    files = {
        "pgvector": RESULTS_DIR / "pgvector_results.json",
        "milvus": RESULTS_DIR / "milvus_results.json",
        "faiss": RESULTS_DIR / "faiss_results.json",
        "batch": RESULTS_DIR / "batch_results.json",
        "caching": RESULTS_DIR / "caching_results.json",
    }
    data = {}
    for key, path in files.items():
        if path.exists():
            with open(path) as f:
                data[key] = json.load(f)
            print(f"  Loaded {key} results ({len(data[key])} records)")
        else:
            print(f"  WARNING: {path} not found — skipping {key} charts")
    return data


def make_comparison_charts(data: dict):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    # Collect all vector-DB results
    vec_results = []
    for key in ("pgvector", "milvus", "faiss"):
        if key in data:
            vec_results.extend(data[key])

    if not vec_results:
        print("  No vector DB results to chart")
        return

    scales = sorted(set(r["scale"] for r in vec_results))
    scale_labels = [f"{s//1000}k" for s in scales]

    # Group by (backend, index_type)
    def get_series(backend, index_type):
        pts = []
        for scale in scales:
            match = [r for r in vec_results
                     if r["backend"] == backend and r["index_type"] == index_type and r["scale"] == scale]
            pts.append(match[0] if match else None)
        return pts

    series_defs = [
        ("pgvector",  "brute_force",    "#2c3e50", "pgvector (brute force)", "o"),
        ("pgvector",  "hnsw",           "#3498db", "pgvector (HNSW)",        "s"),
        ("pgvector",  "sequential_scan","#85c1e9", "pgvector (seq scan)",    "^"),
        ("milvus",    "ivf_flat",       "#e74c3c", "Milvus (IVF_FLAT)",      "D"),
        ("milvus",    "hnsw",           "#c0392b", "Milvus (HNSW)",          "v"),
        ("faiss",     "flat_ip",        "#27ae60", "FAISS (Flat IP)",        "P"),
        ("faiss",     "ivf_flat",       "#1e8449", "FAISS (IVF_FLAT)",       "X"),
    ]

    # ── Chart 1: Query latency (p50) vs scale ────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    for backend, idx_type, color, label, marker in series_defs:
        pts = get_series(backend, idx_type)
        y = [p["query_latency_p50_ms"] if p else None for p in pts]
        valid = [(s, v) for s, v in zip(scale_labels, y) if v is not None]
        if valid:
            xs, ys = zip(*valid)
            ax.plot(xs, ys, marker=marker, color=color, label=label, linewidth=2, markersize=8)
    ax.set_xlabel("Dataset scale", fontsize=12)
    ax.set_ylabel("Query latency p50 (ms)", fontsize=12)
    ax.set_title("Query Latency (p50) by Backend and Scale", fontsize=14, fontweight="bold")
    ax.legend(fontsize=9, ncol=2)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "query_latency_comparison.png", dpi=150)
    plt.close()

    # ── Chart 2: Throughput (QPS) vs scale ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 6))
    for backend, idx_type, color, label, marker in series_defs:
        pts = get_series(backend, idx_type)
        y = [p["throughput_qps"] if p else None for p in pts]
        valid = [(s, v) for s, v in zip(scale_labels, y) if v is not None]
        if valid:
            xs, ys = zip(*valid)
            ax.plot(xs, ys, marker=marker, color=color, label=label, linewidth=2, markersize=8)
    ax.set_xlabel("Dataset scale", fontsize=12)
    ax.set_ylabel("Throughput (queries / second)", fontsize=12)
    ax.set_title("Query Throughput by Backend and Scale", fontsize=14, fontweight="bold")
    ax.legend(fontsize=9, ncol=2)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "throughput_comparison.png", dpi=150)
    plt.close()

    # ── Chart 3: Memory usage ────────────────────────────────────────────────
    if len(scales) >= 1:
        fig, axes = plt.subplots(1, len(scales), figsize=(5 * len(scales), 6), sharey=False)
        if len(scales) == 1:
            axes = [axes]
        for ax, scale, slabel in zip(axes, scales, scale_labels):
            labels_p, values_p, colors_p = [], [], []
            color_map = {s[0]+s[1]: s[2] for s in series_defs}
            for backend, idx_type, color, label, _ in series_defs:
                pts = get_series(backend, idx_type)
                match = next((p for p, s in zip(pts, scales) if p and s == scale), None)
                if match and match.get("memory_usage_mb", 0) > 0:
                    labels_p.append(f"{backend}\n({idx_type})")
                    values_p.append(match["memory_usage_mb"])
                    colors_p.append(color)
            if values_p:
                bars = ax.bar(range(len(values_p)), values_p, color=colors_p, alpha=0.85)
                ax.set_xticks(range(len(labels_p)))
                ax.set_xticklabels(labels_p, rotation=30, ha="right", fontsize=8)
                ax.set_ylabel("Memory (MB)")
                ax.set_title(f"Memory Usage @ {slabel}", fontsize=12, fontweight="bold")
        plt.tight_layout()
        plt.savefig(CHARTS_DIR / "memory_comparison.png", dpi=150)
        plt.close()

    # ── Chart 4: Recall@20 ───────────────────────────────────────────────────
    approx_defs = [
        ("pgvector",  "hnsw",           "#3498db", "pgvector HNSW",      "s"),
        ("milvus",    "ivf_flat",       "#e74c3c", "Milvus IVF_FLAT",    "D"),
        ("milvus",    "hnsw",           "#c0392b", "Milvus HNSW",        "v"),
        ("faiss",     "ivf_flat",       "#1e8449", "FAISS IVF_FLAT",     "X"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    for backend, idx_type, color, label, marker in approx_defs:
        pts = get_series(backend, idx_type)
        y = [p["recall_at_20"] if p else None for p in pts]
        valid = [(s, v) for s, v in zip(scale_labels, y) if v is not None]
        if valid:
            xs, ys = zip(*valid)
            ax.plot(xs, ys, marker=marker, color=color, label=label, linewidth=2, markersize=9)
    ax.axhline(1.0, color="gray", linestyle="--", alpha=0.5, label="Perfect recall")
    ax.set_xlabel("Dataset scale", fontsize=12)
    ax.set_ylabel("Recall@20", fontsize=12)
    ax.set_ylim(0, 1.05)
    ax.set_title("Recall@20 for Approximate Methods", fontsize=14, fontweight="bold")
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "recall_comparison.png", dpi=150)
    plt.close()

    # ── Chart 5: Indexing time ────────────────────────────────────────────────
    indexed_defs = [
        ("pgvector", "hnsw",      "#3498db", "pgvector HNSW"),
        ("milvus",   "ivf_flat",  "#e74c3c", "Milvus IVF_FLAT"),
        ("milvus",   "hnsw",      "#c0392b", "Milvus HNSW"),
        ("faiss",    "ivf_flat",  "#1e8449", "FAISS IVF_FLAT"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    for backend, idx_type, color, label in indexed_defs:
        pts = get_series(backend, idx_type)
        y = [p["indexing_time_seconds"] if p else None for p in pts]
        valid = [(s, v) for s, v in zip(scale_labels, y) if v is not None]
        if valid:
            xs, ys = zip(*valid)
            ax.plot(xs, ys, marker="o", color=color, label=label, linewidth=2, markersize=8)
    ax.set_xlabel("Dataset scale", fontsize=12)
    ax.set_ylabel("Indexing time (seconds)", fontsize=12)
    ax.set_title("Index Build Time by Backend and Scale", fontsize=14, fontweight="bold")
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "indexing_time_comparison.png", dpi=150)
    plt.close()

    print(f"\nComparison charts saved → {CHARTS_DIR}")


def save_combined(data: dict):
    combined = {
        "vector_db": [],
        "batch_pipeline": data.get("batch", []),
        "caching": data.get("caching", []),
    }
    for key in ("pgvector", "milvus", "faiss"):
        combined["vector_db"].extend(data.get(key, []))

    out = RESULTS_DIR / "combined_results.json"
    with open(out, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"Combined results → {out}")


def print_summary(data: dict):
    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)

    if "pgvector" in data or "milvus" in data or "faiss" in data:
        all_vec = []
        for k in ("pgvector", "milvus", "faiss"):
            all_vec.extend(data.get(k, []))
        print(f"\n{'Backend':<12} {'Scale':>6} {'Index':<16} {'p50(ms)':>8} {'p99(ms)':>8} {'QPS':>7} {'Recall':>7}")
        print("-"*70)
        for r in sorted(all_vec, key=lambda x: (x["scale"], x["backend"], x["index_type"])):
            print(f"{r['backend']:<12} {r['scale']:>6} {r['index_type']:<16} "
                  f"{r['query_latency_p50_ms']:>8.1f} {r['query_latency_p99_ms']:>8.1f} "
                  f"{r['throughput_qps']:>7.1f} {r['recall_at_20']:>7.3f}")

    if "caching" in data:
        print(f"\n{'TTL':<10} {'Hit rate':>9} {'Avg resp(ms)':>13} {'Staleness':>10}")
        print("-"*50)
        for r in data["caching"]:
            print(f"{r['ttl_label']:<10} {r['hit_rate']:>8.1%} {r['avg_response_ms']:>13.1f} "
                  f"{r['avg_staleness']:>10.3f}")


def main():
    parser = argparse.ArgumentParser(description="Run all TeamUp benchmarks")
    parser.add_argument("--scale", choices=["1k", "all"], default="all",
                        help="Dataset scale (default: all = 1k + 10k)")
    parser.add_argument("--skip-data-gen", action="store_true",
                        help="Skip generating synthetic data (use existing parquet files)")
    parser.add_argument("--skip-milvus", action="store_true",
                        help="Skip Milvus benchmark (if Milvus is not running)")
    parser.add_argument("--skip-caching", action="store_true",
                        help="Skip caching benchmark")
    parser.add_argument("--charts-only", action="store_true",
                        help="Only regenerate charts from existing result files")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.charts_only:
        print("Regenerating charts from existing results...")
        data = load_results()
        make_comparison_charts(data)
        save_combined(data)
        print_summary(data)
        return

    scale_arg = ["--scale", args.scale]

    # ── Step 1: Generate synthetic data ─────────────────────────────────────
    if not args.skip_data_gen:
        run_script("generate_synthetic_data.py", scale_arg)
    else:
        print("Skipping data generation (--skip-data-gen)")

    # ── Step 2: Vector DB benchmarks ─────────────────────────────────────────
    run_script("bench_pgvector.py", scale_arg)

    if not args.skip_milvus:
        run_script("bench_milvus.py", scale_arg)
    else:
        print("Skipping Milvus benchmark (--skip-milvus)")

    run_script("bench_faiss.py", scale_arg)

    # ── Step 3: Batch pipeline benchmark ─────────────────────────────────────
    run_script("bench_batch_pipeline.py", ["--quick"] if args.scale == "1k" else [])

    # ── Step 3b: Spark pipeline benchmark ────────────────────────────────────
    run_script("bench_spark_pipeline.py", ["--scale", "1k" if args.scale == "1k" else "10k"])

    # ── Step 4: Caching benchmark ─────────────────────────────────────────────
    if not args.skip_caching:
        caching_scale = "1k" if args.scale == "1k" else "10k"
        run_script("bench_caching.py", ["--scale", caching_scale])
    else:
        print("Skipping caching benchmark (--skip-caching)")

    # ── Step 5: Load all results and generate comparison charts ──────────────
    print("\n" + "="*60)
    print("Generating combined comparison charts...")
    data = load_results()
    make_comparison_charts(data)
    save_combined(data)
    print_summary(data)

    print("\n" + "="*60)
    print("All benchmarks complete.")
    print(f"Results  → {RESULTS_DIR}")
    print(f"Charts   → {CHARTS_DIR}")


if __name__ == "__main__":
    main()
