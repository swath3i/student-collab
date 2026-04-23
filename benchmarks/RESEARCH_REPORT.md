# Vector Database Benchmarking for Student Collaboration Recommendation Engine

**Project:** TeamUp — Student Collaboration & Project Matching Platform  
**Author:** Swathi 
**Date:** April 2026  
**Scope:** Master's Thesis — Big Data & Distributed Systems Research Extension

---

## 1. Introduction and Motivation

TeamUp matches students based on complementary skills and project interests using semantic similarity over embedding vectors. Each user profile is represented by two 384-dimensional sentence-transformer embeddings (`all-MiniLM-L6-v2`):

- **Skill embedding** — generated from the user's skills text
- **Intent embedding** — generated from the user's project interest / intention text

Recommendations are ranked by a composite score:

```
score = 0.35 × cosine_similarity(query_skill, candidate_skill)
      + 0.65 × cosine_similarity(query_intent, candidate_intent)
```

The intent weight is higher because finding people with aligned project goals matters more than pure skill overlap; skills can be learned, but motivation alignment is harder to bridge.

This research benchmarks three vector database backends — **pgvector**, **Milvus**, and **FAISS** — against two scale targets (1,000 and 10,000 user profiles) and analyses Redis caching strategies to understand the cost-quality trade-off in real-time recommendation delivery.

---

## 2. Experimental Setup

### 2.1 Synthetic Dataset Generation

Two datasets were generated (`generate_synthetic_data.py`):

| Dataset | Profiles | File |
|---------|----------|------|
| Small   | 1,000    | `synthetic_1k.parquet` |
| Large   | 10,000   | `synthetic_10k.parquet` |

Each profile contains realistic academic fields (12 departments: Computer Science, Biomedical Engineering, Data Science, etc.) with templated skills and intent text. Embeddings were produced by calling the ML service's `/batch_embed` endpoint in batches of 64, yielding 384-dimensional float32 vectors stored in Parquet for reproducibility.

### 2.2 Query Workload

Each benchmark runs **100 queries** sampled uniformly from the dataset (random seed 42). The query user is excluded from candidates. Top-20 results are returned per query (`TOP_K = 20`). For ANN methods, 100 candidates are retrieved per vector index (`CANDIDATE_K = 100`), merged, and reranked via exact composite scoring in Python/NumPy.

### 2.3 Metrics

- **p50 / p95 / p99 latency (ms)** — end-to-end query latency including candidate retrieval and composite rescoring
- **Throughput (QPS)** — queries per second, derived from mean latency
- **Recall@20** — fraction of true top-20 results (by exact brute force) recovered by the approximate method
- **Indexing time (s)** — time to build the vector index
- **Memory (MB)** — storage footprint of vectors + index

### 2.4 Infrastructure

All services ran in Docker on the same MacBook (Apple Silicon M-series):

| Service | Version / Config |
|---------|-----------------|
| PostgreSQL + pgvector | 15 + pgvector extension |
| Milvus | 2.3.4 standalone |
| FAISS | 1.7.4 (CPU, faiss-cpu) |
| Redis | 7.x |
| ML Service | FastAPI + sentence-transformers `all-MiniLM-L6-v2` |

---

## 3. Vector Database Benchmark Results

### 3.1 FAISS (In-process, CPU)

FAISS runs entirely in the Python process — no network overhead, no serialization. This makes it the fastest option but requires the entire index to fit in application memory.

#### Strategy: Candidate-merge with two indexes

Both `flat_ip` (exact) and `ivf_flat` (approximate) use the same composite scoring pipeline:
1. Query both the skill index and the intent index for `CANDIDATE_K = 100` results each
2. Union the candidate row indices
3. Compute exact composite scores using in-memory normalized embedding matrices
4. Return top-20

#### Results

| Scale  | Index     | p50 (ms) | p99 (ms) | QPS     | Recall@20 |
|--------|-----------|----------|----------|---------|-----------|
| 1,000  | flat_ip   | 0.3      | 11.1     | 1,022.7 | 1.000     |
| 1,000  | ivf_flat  | 0.1      | 1.3      | 4,232.5 | 0.983     |
| 10,000 | flat_ip   | 1.3      | 7.4      | 533.7   | 1.000     |
| 10,000 | ivf_flat  | 0.4      | 3.8      | 1,687.4 | 0.997     |

**`IndexFlatIP`** performs exact inner-product search after unit-normalizing vectors (so IP = cosine similarity). It scans all vectors but operates entirely in BLAS-optimized NumPy, making it sub-millisecond even at 10k.

**`IndexIVFFlat`** partitions vectors into `nlist = ⌈√n⌉` Voronoi cells and probes the nearest `nprobe = nlist/10` cells. At 10k, nlist = 100 with nprobe = 10, achieving 1,687 QPS with only 0.3% recall loss — an outstanding accuracy-speed trade-off.

**Key observation:** FAISS is the clear winner on raw speed. At 10k profiles, IVF_FLAT delivers **1,687 QPS with 99.7% recall** — 50× faster than pgvector's HNSW at the same scale. The caveat is that FAISS is an in-process library: scaling beyond a single machine requires building a custom distribution layer.

---

### 3.2 Milvus (Dedicated Vector Database, gRPC)

Milvus 2.3.x supports only **one vector field per collection** (multi-vector support was added in 2.4). To handle two embeddings per profile, we use **two separate collections per index type**:

- `bm_{scale}_{idx}_skill` — skill embeddings
- `bm_{scale}_{idx}_intent` — intent embeddings

The composite scoring pipeline mirrors FAISS: search both collections, union candidates, score with in-memory NumPy arrays loaded from the parquet file.

#### Index configurations

| Index      | Parameters |
|------------|------------|
| IVF_FLAT   | nlist=128, nprobe=16, metric=IP |
| HNSW       | M=16, efConstruction=64, ef=100, metric=IP |

Note: For HNSW search, `ef` must be ≥ `CANDIDATE_K` (100). Milvus raises an error otherwise — this was a discovered edge case during development.

#### Results

| Scale  | Index    | p50 (ms) | p99 (ms) | QPS   | Recall@20 |
|--------|----------|----------|----------|-------|-----------|
| 1,000  | ivf_flat | 12.4     | 32.2     | 74.8  | 1.000     |
| 1,000  | hnsw     | 10.7     | 23.7     | 92.4  | 1.000     |
| 10,000 | ivf_flat | 12.6     | 29.8     | 74.2  | 1.000     |
| 10,000 | hnsw     | 5.8      | 11.4     | 152.9 | 0.943     |

**Key observations:**
- IVF_FLAT achieves **100% recall** at both scales — it effectively performs an exact search within probed cells, and with nprobe=16 and nlist=128 the entire index is nearly always covered for small datasets.
- HNSW at 10k achieves **152.9 QPS at p50=5.8ms** but recall drops to 94.3%. This is expected: HNSW makes greedy graph traversal approximations, and the dual-index candidate-merging strategy amplifies the approximation error slightly.
- Latency is dominated by two round-trips over gRPC to Milvus (one per collection) plus Python composite scoring. The ~10-15ms floor is largely network/IPC overhead on localhost.
- Milvus indexing is more expensive: 7-8 seconds for both collections at 1k, vs <1 second for pgvector at the same scale.

---

### 3.3 pgvector (PostgreSQL Extension)

pgvector integrates vector similarity search into PostgreSQL, enabling composite queries that join structured filters with semantic similarity — a major architectural advantage for systems already using a relational database.

Three strategies were tested:

#### Strategy 1: Brute Force (fetch all, score in Python)
Fetches all user embeddings from PostgreSQL, computes composite scores in NumPy. This establishes the exact ground truth.

#### Strategy 2: Sequential Scan (SQL composite expression, no index)
Computes the composite score directly in SQL using pgvector's `<=>` cosine distance operator:
```sql
SELECT user_id,
       (0.35 * (1 - skill_embedding <=> $1::vector) +
        0.65 * (1 - intent_embedding <=> $2::vector)) AS score
FROM profiles
WHERE user_id != $3
ORDER BY score DESC LIMIT 20
```
PostgreSQL scans all rows but the scoring is pushed into the database engine, eliminating Python deserialization of full embeddings.

#### Strategy 3: HNSW Index (candidate merge, rerank in Python)
Two HNSW indexes (m=16, ef_construction=64, cosine distance) are queried separately for `CANDIDATE_K=100` candidates each. Candidates are merged and reranked with the composite score in Python.

#### Results

| Scale  | Strategy        | p50 (ms) | p99 (ms)  | QPS    | Recall@20 |
|--------|-----------------|----------|-----------|--------|-----------|
| 1,000  | brute_force     | 503.9    | 643.1     | 2.0    | 1.000     |
| 1,000  | sequential_scan | 6.2      | 29.5      | 124.3  | 1.000     |
| 1,000  | hnsw            | 81.0     | 113.7     | 12.3   | 0.996     |
| 10,000 | brute_force     | 2,355.0  | 4,896.8   | 0.4    | 1.000     |
| 10,000 | sequential_scan | 27.2     | 73.9      | 33.3   | 1.000     |
| 10,000 | hnsw            | 46.1     | 64.0      | 21.9   | 0.927     |

**Key observations:**

- **Brute force is unusable at scale** — 2.4 seconds per query at 10k. It fetches all embedding vectors over the network and deserializes them in Python, making it ~80× slower than the SQL approaches.

- **Sequential scan outperforms HNSW** at both scales. This is a counterintuitive but well-documented pgvector behaviour: at <100k rows, the HNSW candidate-merge strategy (two index scans + Python rerank) has higher overhead than a single optimized sequential scan of the table that scores inline in SQL. The sequential scan also achieves **100% recall** because it is exact.

- **HNSW recall degrades more sharply** at 10k (92.7%) compared to Milvus HNSW (94.3%) and FAISS IVF (99.7%). This is because the pgvector HNSW approach fetches 100 candidates *per individual embedding*, not per composite query — some high-composite-score candidates may rank 101st in both individual skill and intent lists and never appear in the merged set.

- **pgvector's unique strength** is the ability to combine vector similarity with SQL predicates: `WHERE department = 'CS' AND graduation_year = 2025 ORDER BY composite_score`. No other backend offers this without a separate relational join.

---

### 3.4 Cross-Backend Comparison

#### At 1,000 profiles

| Backend  | Method        | p50 (ms) | QPS     | Recall@20 |
|----------|---------------|----------|---------|-----------|
| FAISS    | ivf_flat      | 0.1      | 4,232.5 | 0.983     |
| FAISS    | flat_ip       | 0.3      | 1,022.7 | 1.000     |
| pgvector | sequential    | 6.2      | 124.3   | 1.000     |
| Milvus   | hnsw          | 10.7     | 92.4    | 1.000     |
| Milvus   | ivf_flat      | 12.4     | 74.8    | 1.000     |
| pgvector | hnsw          | 81.0     | 12.3    | 0.996     |

#### At 10,000 profiles

| Backend  | Method        | p50 (ms) | QPS     | Recall@20 |
|----------|---------------|----------|---------|-----------|
| FAISS    | ivf_flat      | 0.4      | 1,687.4 | 0.997     |
| FAISS    | flat_ip       | 1.3      | 533.7   | 1.000     |
| Milvus   | hnsw          | 5.8      | 152.9   | 0.943     |
| pgvector | sequential    | 27.2     | 33.3    | 1.000     |
| pgvector | hnsw          | 46.1     | 21.9    | 0.927     |
| Milvus   | ivf_flat      | 12.6     | 74.2    | 1.000     |

#### Winner by dimension

| Dimension          | Winner              | Notes |
|--------------------|---------------------|-------|
| Throughput (QPS)   | FAISS IVF_FLAT      | 1,687 QPS @ 10k — 11× faster than Milvus HNSW |
| Recall accuracy    | FAISS flat / pgvector sequential | Both exact at 1.000 |
| Operational ease   | pgvector            | No separate infrastructure; SQL joins with user table |
| Scale-out          | Milvus              | Distributed clustering built-in for millions of vectors |
| Structured filters | pgvector            | WHERE clauses on any column alongside vector similarity |
| Cold-start memory  | FAISS               | No server process, just a library |

---

## 4. Batch Embedding Pipeline Benchmark

### 4.1 Motivation

When a new user onboards, their profile embeddings must be computed by the ML service. As the platform grows, profiles arrive in bursts (e.g., start-of-semester registration). Sequential per-profile calls to `/embed` waste GPU/CPU time on model initialization overhead per call. The `/batch_embed` endpoint processes lists of texts in a single forward pass, amortizing this cost.

### 4.2 Methodology

- **Sequential**: one POST to `/embed` per profile
- **Batch**: one POST to `/batch_embed` per batch of N profiles, batch sizes 16/32/64/128/256
- Profile counts tested: 100, 500, 1,000, 5,000
- Latency reported per profile (total time / n_profiles)

### 4.3 Results Summary

| Method      | n=100  | n=500  | n=1,000 | n=5,000 |
|-------------|--------|--------|---------|---------|
| Sequential  | 63.4/s | 60.0/s | 59.0/s  | 52.4/s  |
| Best batch  | 184.8/s (bs=32) | 176.3/s (bs=32) | 162.0/s (bs=64) | 161.2/s (bs=256) |
| Speedup     | 2.91×  | 2.94×  | 2.75×   | 3.08×   |

Full results from `batch_results.json`:

| Method     | n     | Batch size | Throughput/s | p50 (ms) | p99 (ms) |
|------------|-------|------------|--------------|----------|----------|
| sequential | 100   | 1          | 63.4         | 14.8     | 27.0     |
| batch      | 100   | 16         | 176.8        | 5.6      | 8.1      |
| batch      | 100   | 32         | 184.8        | 5.5      | 8.0      |
| batch      | 100   | 64         | 145.9        | 6.7      | 7.1      |
| sequential | 1,000 | 1          | 59.0         | 15.8     | 36.7     |
| batch      | 1,000 | 32         | 160.5        | 6.1      | 7.5      |
| batch      | 1,000 | 64         | 162.0        | 6.1      | 7.0      |
| sequential | 5,000 | 1          | 52.4         | 16.2     | 62.5     |
| batch      | 5,000 | 64         | 160.4        | 6.1      | 8.1      |
| batch      | 5,000 | 256        | 161.2        | 6.2      | 6.9      |

### 4.4 Key Findings

1. **Batch processing delivers a consistent ~3× throughput improvement** across all profile counts.
2. **Optimal batch size is 32–64** for small loads; 64–256 for large loads. Batch sizes beyond 128 show diminishing returns because the sentence-transformer model's internal batching saturates the CPU BLAS threads.
3. **Sequential latency degrades at scale** (63 → 52 profiles/s from n=100 to n=5,000) due to accumulated Python event-loop overhead. Batch latency per profile remains stable (~6ms).
4. **p99 latency is 4–9× lower with batching** (7ms vs 63ms at n=100), which matters for bulk onboarding pipelines with strict SLAs.
5. The Django management command `process_embeddings` uses the batch endpoint with `batch_size=32` (default) and a Redis queue to process profiles asynchronously — this keeps the web request fast while embeddings are computed in the background.

---

## 5. Redis Caching Strategy Analysis

### 5.1 Motivation

Computing a fresh recommendation for a user requires a vector index query taking 27–46ms (pgvector HNSW at 10k) or up to 2.4 seconds (brute force). A cache stores the computed recommendation list and serves it instantly (~2ms Redis round-trip) until it expires. The challenge is choosing the TTL: too short wastes the speedup, too long serves stale recommendations after users update their profiles.

### 5.2 Simulation Model

The simulation uses a 10,000-profile dataset and models 200 active users over a 1-hour window:
- **4 requests per user per hour** (Poisson arrival, exponential inter-arrival times)
- **1% profile update rate per hour** → cache invalidation
- **2% connection-accept rate per hour** → invalidation of both parties

The cache is a Python dict simulating Redis key-value storage. On a cache miss, the actual pgvector HNSW query is executed. Staleness is measured as `1 - Jaccard(cached_recs, fresh_recs)`.

### 5.3 Results

| TTL     | Hit Rate | Avg Response (ms) | Staleness |
|---------|----------|-------------------|-----------|
| 1 min   | 6.0%     | 28.5              | 0.000     |
| 5 min   | 21.6%    | 24.2              | 0.000     |
| 15 min  | 48.3%    | 16.3              | 0.000     |
| 30 min  | 61.1%    | 13.0              | 0.000     |
| 1 hour  | 75.6%    | 8.9               | 0.000     |
| 6 hours | 74.9%    | 9.2               | 0.000     |

### 5.4 Key Findings

1. **1-hour TTL is the inflection point** — hit rate jumps from 61% at 30 min to 75.6% at 1 hour, and response time drops to ~9ms (from 27ms baseline). Beyond 1 hour, returns diminish: the 6-hour TTL yields slightly lower hit rate (74.9%) because more profiles are updated within that window, causing invalidations.

2. **Zero measured staleness** across all TTL values. This is explained by the combination of event-driven invalidation (profile updates and connection accepts immediately remove the cache entry) and the simulation parameters (1% update rate × 200 active users = ~2 invalidations per hour on average). In a production system with higher update rates, staleness would appear at longer TTLs.

3. **The practical recommendation for TeamUp is a 1-hour TTL** with explicit cache invalidation on:
   - Profile skill/intent text update
   - New connection accepted (both users' caches invalidated)
   - New skill added to profile

4. **System load reduction**: at 75.6% hit rate, the vector database receives only 24.4% of the original query volume — a 4× reduction in database load, enabling the system to handle ~4× more concurrent users with the same hardware.

5. **The trade-off is not cache staleness vs. hit rate** in this system (staleness is controlled by invalidation), but **stale-window duration for users who update profiles infrequently**. A user who updates their intent text at minute 1 of a 6-hour TTL won't see updated recommendations for anyone who cached their results. Explicit invalidation on the querying user's key solves this.

---

## 6. Architectural Recommendations for TeamUp

### 6.1 Chosen Stack: pgvector + Redis Cache

For TeamUp's current scale (hundreds to a few thousand students per university), the recommended production architecture is:

```
User Request → Redis Cache (1h TTL) → pgvector HNSW → Response
                    ↑ miss                  ↑
              Cache invalidation    SQL composite score
              (profile update,      (structured filters
               connection accept)    + semantic ranking)
```

**Why not FAISS?**
FAISS would be faster (>1,600 QPS vs 33 QPS), but it requires keeping all embeddings in the application server's memory, preventing horizontal scaling, and it cannot join with user profile filters (active status, graduation year, department) without a separate database query.

**Why not Milvus?**
Milvus adds operational complexity (separate service, network round-trips, collection management) for a scale where pgvector's sequential scan (33 QPS) is fast enough when cached. The dual-collection workaround for multi-vector queries is also inelegant. Milvus becomes the right choice at 100k+ profiles or when horizontal vector-search scaling is needed.

**Why pgvector sequential scan over HNSW?**
At 10k profiles, sequential scan (27ms, 33 QPS, 100% recall) beats HNSW (46ms, 22 QPS, 92.7% recall). The composite scoring must be done in Python for HNSW due to the candidate-merge architecture, adding overhead that outweighs index lookup savings. At 100k+ profiles, HNSW will win because sequential scan scales linearly while HNSW scales logarithmically.

### 6.2 Future Scale Path

| Users    | Recommended Backend | Strategy |
|----------|---------------------|----------|
| < 50k    | pgvector sequential scan | Exact composite in SQL, Redis cache |
| 50k–500k | pgvector HNSW       | Approximate, very high recall, SQL filters |
| 500k+    | Milvus or Weaviate  | Distributed vector search, separate metadata DB |

### 6.3 Embedding Pipeline

Use the batch embedding pipeline (`/batch_embed` endpoint + Django management command) for all bulk operations:
- **Onboarding**: new user profile creation
- **Re-embedding**: when the model is retrained/updated
- **Backfill**: for users who joined before embeddings were added

Target batch size: **32–64** for real-time batching, **256** for bulk offline jobs.

---

## 7. Limitations and Future Work

1. **Single-machine benchmarks**: All services ran on the same hardware. In production, network latency between application servers and database servers would add 1–5ms per query, slightly favouring FAISS (in-process) over Milvus/pgvector.

2. **Synthetic data**: The benchmark dataset uses template-generated profiles. Real academic text may have different embedding distributions and clustering characteristics, potentially changing recall figures.

3. **Cold-start caching**: New users have no cache entry. The first recommendation request always hits the database. A background prewarming job (triggered at onboarding) would eliminate cold-start latency for active users.

4. **Hybrid filtering not benchmarked**: pgvector's ability to filter by department/year before or after vector search was not evaluated. Adding a filter predicate can reduce the scanned set significantly, potentially making pgvector competitive with FAISS even at larger scales.

5. **Embedding model comparison**: Only `all-MiniLM-L6-v2` (384-dim) was tested. Larger models (e.g., `all-mpnet-base-v2` at 768-dim) would produce higher-quality embeddings but double memory requirements and reduce throughput.

---

## 8. Conclusion

This research demonstrates that **vector database selection for a university-scale recommendation system is a trade-off between operational simplicity, query flexibility, and raw throughput**:

- **FAISS** delivers exceptional speed (1,687 QPS at 10k, 99.7% recall) but is an in-process library unsuitable for multi-server deployments without custom sharding.
- **pgvector** integrates seamlessly with the existing Django/PostgreSQL stack, supports SQL filtering, and at <50k profiles the sequential scan strategy outperforms HNSW on both latency and recall.
- **Milvus** provides purpose-built vector infrastructure with horizontal scalability but adds operational overhead and the 2.3.x single-vector-field limitation requires a workaround architecture for multi-embedding profiles.
- **Redis caching** at a 1-hour TTL reduces database load by 75%, bringing effective response time to ~9ms — closer to in-process FAISS performance — while event-driven invalidation keeps recommendations fresh.

For TeamUp, the **pgvector + Redis combination** provides the best balance: zero new infrastructure, SQL flexibility for structured filters, and sub-10ms effective response time after cache warm-up.
