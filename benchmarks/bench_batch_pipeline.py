"""
Batch embedding pipeline benchmark.

Compares:
  - Sequential: call /embed once per profile
  - Batch:      call /batch_embed with varying batch sizes (16, 32, 64, 128, 256)

Measures: total time, throughput (profiles/sec), per-profile latency.
Profile counts tested: 100, 500, 1000, 5000.

Usage:
    python bench_batch_pipeline.py
    python bench_batch_pipeline.py --ml-url http://localhost:8001
"""

import argparse
import json
import os
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import requests
from tqdm import tqdm

ML_SERVICE_URL = os.environ.get("ML_SERVICE_URL", "http://localhost:8001")
RESULTS_DIR = Path(__file__).parent / "results"
CHARTS_DIR = RESULTS_DIR / "charts"

PROFILE_COUNTS = [100, 500, 1000, 5000]
BATCH_SIZES = [16, 32, 64, 128, 256]

SAMPLE_TEXTS = [
    "Python machine learning PyTorch deep learning NLP transformers BERT data pipelines",
    "Java distributed systems Kafka Kubernetes Docker microservices gRPC Spring Boot Redis",
    "React TypeScript Node.js GraphQL MongoDB AWS serverless CI/CD frontend development",
    "C++ CUDA GPU computing parallel algorithms HPC OpenMPI systems programming performance",
    "MATLAB signal processing control systems Simulink PID FEA structural analysis ANSYS",
    "R econometrics Bayesian statistics causal inference panel data regression discontinuity",
    "Python bioinformatics RNA-seq genome assembly GATK variant calling scRNA-seq Biopython",
    "Swift iOS SwiftUI CoreML ARKit mobile development UIKit Xcode CocoaPods XCTest",
    "Go Rust systems programming memory safety concurrency async networking gRPC protocol buffers",
    "SQL dbt Airflow Snowflake BigQuery dimensional modeling data warehousing ETL pipelines",
    "FPGA VHDL Verilog digital design RTL synthesis timing analysis Xilinx embedded systems",
    "Julia scientific computing ODE solvers automatic differentiation numerical methods SciML",
]


def check_ml_service():
    try:
        resp = requests.get(f"{ML_SERVICE_URL}/health", timeout=5)
        if not resp.json().get("model_loaded"):
            raise RuntimeError("ML service model not loaded")
        print(f"ML service ready at {ML_SERVICE_URL}")
    except requests.exceptions.ConnectionError:
        raise RuntimeError(f"Cannot reach ML service at {ML_SERVICE_URL}")


def make_texts(n: int) -> list[str]:
    texts = []
    for i in range(n):
        base = SAMPLE_TEXTS[i % len(SAMPLE_TEXTS)]
        texts.append(f"{base} profile_{i}")
    return texts


def benchmark_sequential(texts: list[str]) -> dict:
    n = len(texts)
    latencies = []
    t_total = time.perf_counter()
    for text in tqdm(texts, desc=f"  sequential n={n}", leave=False):
        t0 = time.perf_counter()
        resp = requests.post(f"{ML_SERVICE_URL}/embed", json={"text": text}, timeout=30)
        resp.raise_for_status()
        latencies.append((time.perf_counter() - t0) * 1000)
    total_time = time.perf_counter() - t_total
    return {
        "method": "sequential",
        "n_profiles": n,
        "batch_size": 1,
        "total_time_s": total_time,
        "throughput_per_s": n / total_time,
        "mean_latency_ms": float(np.mean(latencies)),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p99_ms": float(np.percentile(latencies, 99)),
    }


def benchmark_batch(texts: list[str], batch_size: int) -> dict:
    n = len(texts)
    latencies = []
    t_total = time.perf_counter()
    for start in tqdm(range(0, n, batch_size), desc=f"  batch={batch_size} n={n}", leave=False):
        chunk = texts[start : start + batch_size]
        t0 = time.perf_counter()
        resp = requests.post(f"{ML_SERVICE_URL}/batch_embed", json={"texts": chunk}, timeout=120)
        resp.raise_for_status()
        elapsed = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed / len(chunk))  # per-profile latency
    total_time = time.perf_counter() - t_total
    return {
        "method": "batch",
        "n_profiles": n,
        "batch_size": batch_size,
        "total_time_s": total_time,
        "throughput_per_s": n / total_time,
        "mean_latency_ms": float(np.mean(latencies)),
        "p50_ms": float(np.percentile(latencies, 50)),
        "p99_ms": float(np.percentile(latencies, 99)),
    }


def plot_results(results: list[dict]):
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    # ── Chart 1: Sequential vs best-batch throughput ─────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    counts = sorted(set(r["n_profiles"] for r in results))
    seq_throughput = [
        next(r["throughput_per_s"] for r in results if r["n_profiles"] == n and r["method"] == "sequential")
        for n in counts
    ]
    best_batch = [
        max(r["throughput_per_s"] for r in results if r["n_profiles"] == n and r["method"] == "batch")
        for n in counts
    ]
    x = np.arange(len(counts))
    w = 0.35
    ax.bar(x - w/2, seq_throughput, w, label="Sequential (/embed)", color="#e74c3c", alpha=0.85)
    ax.bar(x + w/2, best_batch, w, label="Batch best (/batch_embed)", color="#2ecc71", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([str(c) for c in counts])
    ax.set_xlabel("Number of profiles", fontsize=12)
    ax.set_ylabel("Throughput (profiles / second)", fontsize=12)
    ax.set_title("Sequential vs Batch Embedding Throughput", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "batch_vs_sequential.png", dpi=150)
    plt.close()

    # ── Chart 2: Throughput vs batch size for each n ─────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    batch_results = [r for r in results if r["method"] == "batch"]
    for n in counts:
        sizes = sorted(set(r["batch_size"] for r in batch_results if r["n_profiles"] == n))
        tput = [
            next(r["throughput_per_s"] for r in batch_results if r["n_profiles"] == n and r["batch_size"] == bs)
            for bs in sizes
        ]
        ax.plot(sizes, tput, marker="o", label=f"n={n}", linewidth=2)
    ax.set_xlabel("Batch size", fontsize=12)
    ax.set_ylabel("Throughput (profiles / second)", fontsize=12)
    ax.set_title("Throughput vs Batch Size", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "batch_size_throughput.png", dpi=150)
    plt.close()

    # ── Chart 3: Total processing time vs n (sequential vs batch=64) ─────────
    fig, ax = plt.subplots(figsize=(9, 5))
    seq_times = [
        next(r["total_time_s"] for r in results if r["n_profiles"] == n and r["method"] == "sequential")
        for n in counts
    ]
    b64_times = [
        next((r["total_time_s"] for r in results if r["n_profiles"] == n and r["method"] == "batch" and r["batch_size"] == 64), None)
        for n in counts
    ]
    ax.plot(counts, seq_times, marker="o", label="Sequential", color="#e74c3c", linewidth=2)
    valid = [(n, t) for n, t in zip(counts, b64_times) if t is not None]
    if valid:
        ns, ts = zip(*valid)
        ax.plot(ns, ts, marker="s", label="Batch (size=64)", color="#2ecc71", linewidth=2)
    ax.set_xlabel("Number of profiles", fontsize=12)
    ax.set_ylabel("Total processing time (seconds)", fontsize=12)
    ax.set_title("Processing Time: Sequential vs Batch", fontsize=14, fontweight="bold")
    ax.legend()
    plt.tight_layout()
    plt.savefig(CHARTS_DIR / "batch_processing_time.png", dpi=150)
    plt.close()

    print(f"Charts saved → {CHARTS_DIR}")


def main():
    parser = argparse.ArgumentParser(description="Batch embedding pipeline benchmark")
    parser.add_argument("--ml-url", default=None)
    parser.add_argument("--quick", action="store_true", help="Only test n=100,500 for speed")
    args = parser.parse_args()

    global ML_SERVICE_URL
    if args.ml_url:
        ML_SERVICE_URL = args.ml_url

    check_ml_service()

    counts = [100, 500] if args.quick else PROFILE_COUNTS
    results = []

    for n in counts:
        texts = make_texts(n)
        print(f"\nBenchmarking n={n} profiles...")

        print("  Sequential method...")
        results.append(benchmark_sequential(texts))

        for bs in BATCH_SIZES:
            if bs > n:
                continue
            results.append(benchmark_batch(texts, bs))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "batch_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    plot_results(results)

    print("\nSummary (n=1000):")
    for r in results:
        if r["n_profiles"] == 1000 or (1000 not in [x["n_profiles"] for x in results] and r["n_profiles"] == max(r2["n_profiles"] for r2 in results)):
            label = f"sequential" if r["method"] == "sequential" else f"batch-{r['batch_size']}"
            print(f"  {label:<15} {r['throughput_per_s']:6.1f} profiles/s  total={r['total_time_s']:.1f}s")
            break


if __name__ == "__main__":
    main()
