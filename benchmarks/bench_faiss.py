"""
FAISS benchmark for TeamUp recommendation queries.

Tests two index types:
  - IndexFlatIP  : exact brute-force (unit-normalised vectors, IP = cosine)
  - IndexIVFFlat : approximate with IVF partitioning

Both use candidate-merging: skill index + intent index queried separately,
candidates scored on composite (0.35 * skill_sim + 0.65 * intent_sim).

Usage:
    python bench_faiss.py --scale 1k
    python bench_faiss.py --scale 10k
    python bench_faiss.py --scale all
"""

import argparse
import json
import os
import time
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import psutil
from tqdm import tqdm

DATA_DIR = Path(__file__).parent / "data"
RESULTS_DIR = Path(__file__).parent / "results"
NUM_QUERIES = 100
TOP_K = 20
CANDIDATE_K = 100
SKILL_WEIGHT = 0.35
INTENT_WEIGHT = 0.65
DIM = 384


def load_parquet(scale: str) -> pd.DataFrame:
    path = DATA_DIR / f"synthetic_{scale}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}\nRun generate_synthetic_data.py first.")
    return pd.read_parquet(path)


def normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return matrix / norms


def build_flat_indexes(skill_embs: np.ndarray, intent_embs: np.ndarray):
    idx_skill = faiss.IndexFlatIP(DIM)
    idx_intent = faiss.IndexFlatIP(DIM)
    idx_skill.add(skill_embs)
    idx_intent.add(intent_embs)
    return idx_skill, idx_intent


def build_ivf_indexes(skill_embs: np.ndarray, intent_embs: np.ndarray, n: int):
    nlist = max(1, int(np.sqrt(n)))

    quantizer_s = faiss.IndexFlatIP(DIM)
    idx_skill = faiss.IndexIVFFlat(quantizer_s, DIM, nlist, faiss.METRIC_INNER_PRODUCT)

    quantizer_i = faiss.IndexFlatIP(DIM)
    idx_intent = faiss.IndexIVFFlat(quantizer_i, DIM, nlist, faiss.METRIC_INNER_PRODUCT)

    idx_skill.train(skill_embs)
    idx_intent.train(intent_embs)
    idx_skill.add(skill_embs)
    idx_intent.add(intent_embs)
    idx_skill.nprobe = max(1, nlist // 10)
    idx_intent.nprobe = max(1, nlist // 10)
    return idx_skill, idx_intent


def query_composite(
    idx_skill, idx_intent,
    all_skill_norm: np.ndarray, all_intent_norm: np.ndarray,
    q_skill_norm: np.ndarray, q_intent_norm: np.ndarray,
    query_row_idx: int,
) -> list[int]:
    qs = q_skill_norm.reshape(1, -1)
    qi = q_intent_norm.reshape(1, -1)

    _, skill_ids = idx_skill.search(qs, CANDIDATE_K + 1)
    _, intent_ids = idx_intent.search(qi, CANDIDATE_K + 1)

    candidates = set(skill_ids[0].tolist()) | set(intent_ids[0].tolist())
    candidates.discard(-1)
    candidates.discard(query_row_idx)

    cand_list = list(candidates)
    if not cand_list:
        return []

    cand_arr = np.array(cand_list)
    skill_vecs = all_skill_norm[cand_arr]
    intent_vecs = all_intent_norm[cand_arr]

    skill_sims = skill_vecs @ q_skill_norm
    intent_sims = intent_vecs @ q_intent_norm
    composite = SKILL_WEIGHT * skill_sims + INTENT_WEIGHT * intent_sims

    top_idx = np.argpartition(composite, -min(TOP_K, len(composite)))[-min(TOP_K, len(composite)):]
    top_idx = top_idx[np.argsort(composite[top_idx])[::-1]]
    return [cand_arr[i] for i in top_idx]


def get_process_memory_mb() -> float:
    return psutil.Process().memory_info().rss / 1048576


def compute_recall(ground_truth: list[list[int]], approx: list[list[int]]) -> float:
    hits = sum(len(set(gt) & set(ap)) for gt, ap in zip(ground_truth, approx))
    return hits / (len(ground_truth) * TOP_K)


def benchmark_scale(df: pd.DataFrame, scale: str) -> list[dict]:
    n = len(df)
    print(f"\n── FAISS @ {scale} ({n:,} profiles) ──")

    skill_embs = np.array(df["skill_embedding"].tolist(), dtype=np.float32)
    intent_embs = np.array(df["intent_embedding"].tolist(), dtype=np.float32)
    skill_norm = normalise(skill_embs)
    intent_norm = normalise(intent_embs)

    query_indices = df.sample(n=NUM_QUERIES, random_state=42).index.tolist()
    query_users = [
        {"row_idx": i, "skill": skill_norm[i], "intent": intent_norm[i]}
        for i in query_indices
    ]

    results = []

    # ── IndexFlatIP (exact brute force) ─────────────────────────────────────
    print("  Building IndexFlatIP (exact)...")
    mem_before = get_process_memory_mb()
    t0 = time.perf_counter()
    idx_s_flat, idx_i_flat = build_flat_indexes(skill_norm, intent_norm)
    indexing_time_flat = time.perf_counter() - t0
    mem_after = get_process_memory_mb()
    mem_flat = mem_after - mem_before

    gt_results = []
    flat_latencies = []
    for qu in tqdm(query_users, desc="  flat_ip queries", leave=False):
        t0 = time.perf_counter()
        top = query_composite(idx_s_flat, idx_i_flat, skill_norm, intent_norm,
                              qu["skill"], qu["intent"], qu["row_idx"])
        flat_latencies.append((time.perf_counter() - t0) * 1000)
        gt_results.append(top)

    flat_latencies.sort()
    print(f"  Flat p50={np.percentile(flat_latencies, 50):.1f}ms  "
          f"p99={np.percentile(flat_latencies, 99):.1f}ms")

    results.append({
        "backend": "faiss",
        "scale": n,
        "index_type": "flat_ip",
        "indexing_time_seconds": indexing_time_flat,
        "memory_usage_mb": mem_flat,
        "query_latency_p50_ms": float(np.percentile(flat_latencies, 50)),
        "query_latency_p95_ms": float(np.percentile(flat_latencies, 95)),
        "query_latency_p99_ms": float(np.percentile(flat_latencies, 99)),
        "throughput_qps": float(1000 / np.mean(flat_latencies)),
        "recall_at_20": 1.0,
        "num_queries": NUM_QUERIES,
    })

    del idx_s_flat, idx_i_flat

    # ── IndexIVFFlat (approximate) ──────────────────────────────────────────
    print("  Building IndexIVFFlat (approximate)...")
    mem_before = get_process_memory_mb()
    t0 = time.perf_counter()
    idx_s_ivf, idx_i_ivf = build_ivf_indexes(skill_norm, intent_norm, n)
    indexing_time_ivf = time.perf_counter() - t0
    mem_after = get_process_memory_mb()
    mem_ivf = mem_after - mem_before
    print(f"  IVF indexing time: {indexing_time_ivf:.2f}s")

    ivf_latencies = []
    ivf_results = []
    for qu in tqdm(query_users, desc="  ivf_flat queries", leave=False):
        t0 = time.perf_counter()
        top = query_composite(idx_s_ivf, idx_i_ivf, skill_norm, intent_norm,
                              qu["skill"], qu["intent"], qu["row_idx"])
        ivf_latencies.append((time.perf_counter() - t0) * 1000)
        ivf_results.append(top)

    recall = compute_recall(gt_results, ivf_results)
    ivf_latencies.sort()
    print(f"  IVF p50={np.percentile(ivf_latencies, 50):.1f}ms  "
          f"p99={np.percentile(ivf_latencies, 99):.1f}ms  recall={recall:.4f}")

    results.append({
        "backend": "faiss",
        "scale": n,
        "index_type": "ivf_flat",
        "indexing_time_seconds": indexing_time_ivf,
        "memory_usage_mb": mem_ivf,
        "query_latency_p50_ms": float(np.percentile(ivf_latencies, 50)),
        "query_latency_p95_ms": float(np.percentile(ivf_latencies, 95)),
        "query_latency_p99_ms": float(np.percentile(ivf_latencies, 99)),
        "throughput_qps": float(1000 / np.mean(ivf_latencies)),
        "recall_at_20": recall,
        "num_queries": NUM_QUERIES,
    })

    return results


def main():
    parser = argparse.ArgumentParser(description="FAISS benchmark")
    parser.add_argument("--scale", choices=["1k", "10k", "all"], default="1k")
    args = parser.parse_args()

    to_run = ["1k", "10k"] if args.scale == "all" else [args.scale]

    all_results = []
    for scale in to_run:
        df = load_parquet(scale)
        results = benchmark_scale(df, scale)
        all_results.extend(results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "faiss_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    for r in all_results:
        print(f"  {r['backend']} | {r['scale']:>6} | {r['index_type']:<10} | "
              f"p50={r['query_latency_p50_ms']:6.1f}ms  p99={r['query_latency_p99_ms']:7.1f}ms  "
              f"qps={r['throughput_qps']:6.1f}  recall={r['recall_at_20']:.3f}")


if __name__ == "__main__":
    main()
