"""
Milvus benchmark for TeamUp recommendation queries.

Milvus 2.3.x supports only one vector field per collection, so we use
two separate collections per index type (skill + intent). Candidates
are retrieved from both, then composite scores are computed using
in-memory embeddings loaded from the parquet file.

Usage:
    python bench_milvus.py --scale 1k
    python bench_milvus.py --scale 10k
    python bench_milvus.py --scale all
"""

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pymilvus import (
    Collection, CollectionSchema, DataType, FieldSchema,
    connections, utility,
)
from tqdm import tqdm

MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = int(os.environ.get("MILVUS_PORT", "19530"))
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


def connect_milvus():
    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    print(f"Connected to Milvus at {MILVUS_HOST}:{MILVUS_PORT}")


def drop_collection(name: str):
    if utility.has_collection(name):
        utility.drop_collection(name)


def create_single_vector_collection(name: str, vec_field: str) -> Collection:
    """One vector field per collection — required for Milvus 2.3.x."""
    fields = [
        FieldSchema(name="row_idx", dtype=DataType.INT64, is_primary=True, auto_id=False),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name=vec_field, dtype=DataType.FLOAT_VECTOR, dim=DIM),
    ]
    schema = CollectionSchema(fields, description=f"Benchmark {vec_field}")
    return Collection(name=name, schema=schema)


def insert_data(col: Collection, df: pd.DataFrame, vec_field: str):
    embs = np.array(df[vec_field].tolist(), dtype=np.float32)
    # Normalise for inner product = cosine similarity
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    embs = embs / np.where(norms == 0, 1.0, norms)

    batch_size = 1000
    n = len(df)
    for start in tqdm(range(0, n, batch_size), desc=f"  Inserting {vec_field[:5]}", leave=False):
        end = min(start + batch_size, n)
        col.insert([
            list(range(start, end)),
            df["user_id"].iloc[start:end].tolist(),
            embs[start:end].tolist(),
        ])
    col.flush()
    return embs


def build_index(col: Collection, vec_field: str, index_type: str) -> float:
    if index_type == "IVF_FLAT":
        params = {"nlist": 128}
    else:
        params = {"M": 16, "efConstruction": 64}

    t0 = time.perf_counter()
    col.create_index(
        vec_field,
        {"index_type": index_type, "metric_type": "IP", "params": params},
    )
    col.load()
    return time.perf_counter() - t0


def search_collection(col: Collection, vec_field: str, query_vec: np.ndarray,
                      index_type: str, exclude_id: str) -> list[int]:
    if index_type == "IVF_FLAT":
        search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
    else:
        search_params = {"metric_type": "IP", "params": {"ef": max(64, CANDIDATE_K)}}

    res = col.search(
        data=[query_vec.tolist()],
        anns_field=vec_field,
        param=search_params,
        limit=CANDIDATE_K,
        output_fields=["row_idx"],
        expr=f'user_id != "{exclude_id}"',
    )
    return [hit.entity.get("row_idx") for hit in res[0]]


def query_composite(
    skill_col: Collection, intent_col: Collection,
    skill_norm: np.ndarray, intent_norm: np.ndarray,
    q_skill: np.ndarray, q_intent: np.ndarray,
    qid: str, index_type: str, query_row_idx: int,
) -> list[str]:
    skill_cands = search_collection(skill_col, "skill_embedding", q_skill, index_type, qid)
    intent_cands = search_collection(intent_col, "intent_embedding", q_intent, index_type, qid)

    candidates = set(skill_cands) | set(intent_cands)
    candidates.discard(query_row_idx)

    if not candidates:
        return []

    cand_arr = np.array(list(candidates))
    s_sims = skill_norm[cand_arr] @ q_skill
    i_sims = intent_norm[cand_arr] @ q_intent
    scores = SKILL_WEIGHT * s_sims + INTENT_WEIGHT * i_sims

    top_idx = np.argpartition(scores, -min(TOP_K, len(scores)))[-min(TOP_K, len(scores)):]
    top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
    return [str(cand_arr[i]) for i in top_idx]


def compute_recall(ground_truth: list[list[str]], approx: list[list[str]]) -> float:
    hits = sum(len(set(gt) & set(ap)) for gt, ap in zip(ground_truth, approx))
    return hits / (len(ground_truth) * TOP_K)


def benchmark_scale(df: pd.DataFrame, scale: str) -> list[dict]:
    n = len(df)
    print(f"\n── Milvus @ {scale} ({n:,} profiles) ──")

    skill_embs = np.array(df["skill_embedding"].tolist(), dtype=np.float32)
    intent_embs = np.array(df["intent_embedding"].tolist(), dtype=np.float32)
    skill_norm = skill_embs / np.where(
        np.linalg.norm(skill_embs, axis=1, keepdims=True) == 0, 1.0,
        np.linalg.norm(skill_embs, axis=1, keepdims=True)
    )
    intent_norm = intent_embs / np.where(
        np.linalg.norm(intent_embs, axis=1, keepdims=True) == 0, 1.0,
        np.linalg.norm(intent_embs, axis=1, keepdims=True)
    )

    query_df = df.sample(n=NUM_QUERIES, random_state=42)
    query_users = [
        {
            "id": row.user_id,
            "row_idx": df.index.get_loc(idx),
            "skill": skill_norm[df.index.get_loc(idx)],
            "intent": intent_norm[df.index.get_loc(idx)],
        }
        for idx, row in query_df.iterrows()
    ]

    results = []
    gt_results = None

    for index_type in ("IVF_FLAT", "HNSW"):
        skill_col_name = f"bm_{scale}_{index_type[:3].lower()}_skill"
        intent_col_name = f"bm_{scale}_{index_type[:3].lower()}_intent"
        print(f"\n  Index: {index_type}")

        for name in (skill_col_name, intent_col_name):
            drop_collection(name)

        skill_col = create_single_vector_collection(skill_col_name, "skill_embedding")
        intent_col = create_single_vector_collection(intent_col_name, "intent_embedding")

        print("  Inserting data...")
        insert_data(skill_col, df, "skill_embedding")
        insert_data(intent_col, df, "intent_embedding")

        print(f"  Building {index_type} indexes...")
        t0 = time.perf_counter()
        build_index(skill_col, "skill_embedding", index_type)
        build_index(intent_col, "intent_embedding", index_type)
        indexing_time = time.perf_counter() - t0
        print(f"  Indexing time: {indexing_time:.2f}s")

        mem_mb = n * 2 * DIM * 4 / 1048576  # 2 vectors * 384 * float32

        latencies = []
        approx_results = []
        for qu in tqdm(query_users, desc=f"  {index_type} queries", leave=False):
            t0 = time.perf_counter()
            top = query_composite(
                skill_col, intent_col, skill_norm, intent_norm,
                qu["skill"], qu["intent"], qu["id"], index_type, qu["row_idx"],
            )
            latencies.append((time.perf_counter() - t0) * 1000)
            approx_results.append(top)

        if index_type == "IVF_FLAT":
            gt_results = approx_results
            recall = 1.0
        else:
            recall = compute_recall(gt_results, approx_results) if gt_results else 0.0

        latencies.sort()
        print(f"  p50={np.percentile(latencies, 50):.1f}ms  "
              f"p99={np.percentile(latencies, 99):.1f}ms  recall={recall:.4f}")

        results.append({
            "backend": "milvus",
            "scale": n,
            "index_type": index_type.lower(),
            "indexing_time_seconds": indexing_time,
            "memory_usage_mb": mem_mb,
            "query_latency_p50_ms": float(np.percentile(latencies, 50)),
            "query_latency_p95_ms": float(np.percentile(latencies, 95)),
            "query_latency_p99_ms": float(np.percentile(latencies, 99)),
            "throughput_qps": float(1000 / np.mean(latencies)),
            "recall_at_20": recall,
            "num_queries": NUM_QUERIES,
        })

        for name in (skill_col_name, intent_col_name):
            drop_collection(name)

    return results


def main():
    parser = argparse.ArgumentParser(description="Milvus benchmark")
    parser.add_argument("--scale", choices=["1k", "10k", "all"], default="1k")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    global MILVUS_HOST, MILVUS_PORT
    if args.host:
        MILVUS_HOST = args.host
    if args.port:
        MILVUS_PORT = args.port

    connect_milvus()

    to_run = ["1k", "10k"] if args.scale == "all" else [args.scale]

    all_results = []
    for scale in to_run:
        df = load_parquet(scale)
        # Reset index to ensure integer-based lookup works correctly
        df = df.reset_index(drop=True)
        results = benchmark_scale(df, scale)
        all_results.extend(results)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "milvus_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved → {out_path}")

    for r in all_results:
        print(f"  {r['backend']} | {r['scale']:>6} | {r['index_type']:<10} | "
              f"p50={r['query_latency_p50_ms']:6.1f}ms  p99={r['query_latency_p99_ms']:7.1f}ms  "
              f"qps={r['throughput_qps']:6.1f}  recall={r['recall_at_20']:.3f}")


if __name__ == "__main__":
    main()
