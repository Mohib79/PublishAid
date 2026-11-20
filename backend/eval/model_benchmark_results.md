# Asymmetric Retrieval & Hybrid BM25 Model Benchmark

- **Date**: 2026-11-20
- **Catalog**: 50 journals (chunked sliding windows for >512 tokens, intact natural text)
- **Test Cases**: 20 manuscripts

| Model | Mode | Top-1 | Top-3 | Top-5 | MRR | Mean Top Cos | Mean Min Cos | Mean 1-5 Gap |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Okapi BM25 Only` | Lexical | **25.0%** (5/20) | 45.0% (9/20) | 50.0% (10/20) | **0.3876** | 0.0000 | 0.0000 | 0.4635 |
| `BAAI/bge-base-en-v1.5` | Dense Only (1.0) | **30.0%** (6/20) | 55.0% (11/20) | 65.0% (13/20) | **0.4596** | 0.6261 | 0.4088 | 0.0644 |
| `BAAI/bge-base-en-v1.5` | Hybrid (0.7 Norm-Cos + 0.3 BM25) | **25.0%** (5/20) | 60.0% (12/20) | 75.0% (15/20) | **0.4427** | 0.6100 | 0.4088 | 0.2585 |
| `sentence-transformers/all-mpnet-base-v2` | Dense Only (1.0) | **40.0%** (8/20) | 60.0% (12/20) | 80.0% (16/20) | **0.5467** | 0.3890 | -0.0237 | 0.1308 |
| `sentence-transformers/all-mpnet-base-v2` | Hybrid (0.7 Norm-Cos + 0.3 BM25) | **35.0%** (7/20) | 65.0% (13/20) | 85.0% (17/20) | **0.5437** | 0.3702 | -0.0237 | 0.3008 |
| `allenai/specter2_base` | Dense Only (1.0) | **30.0%** (6/20) | 45.0% (9/20) | 65.0% (13/20) | **0.4601** | 0.8589 | 0.7383 | 0.0269 |
| `allenai/specter2_base` | Hybrid (0.7 Norm-Cos + 0.3 BM25) | **35.0%** (7/20) | 45.0% (9/20) | 70.0% (14/20) | **0.4820** | 0.8450 | 0.7383 | 0.1991 |
| `allenai-specter` | Dense Only (1.0) | **45.0%** (9/20) | 60.0% (12/20) | 75.0% (15/20) | **0.5718** | 0.8050 | 0.5944 | 0.0413 |
| `allenai-specter` | Hybrid (0.7 Norm-Cos + 0.3 BM25) | **45.0%** (9/20) | 55.0% (11/20) | 75.0% (15/20) | **0.5674** | 0.7968 | 0.5944 | 0.2495 |
