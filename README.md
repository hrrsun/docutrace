# DocuTrace

**Local-first document QA with verifiable citations.**
Every answer must be traceable to a page, table row, paragraph, or worksheet — or it is not returned.

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/pytest-22%20passed-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## Why

Enterprise document QA fails for two reasons that are rarely solved together:

1. **Data cannot leave the intranet.** Cloud LLM APIs are not an option.
2. **An answer that cannot be checked is worthless.** A summary is not evidence — a page number and a table row is.

DocuTrace is built for the second requirement first. It runs entirely on a local Ollama endpoint, retrieves with a self-implemented hybrid ranker, and attaches a citation ledger to every generated sentence.

## Features

**Evidence grounding**
- Structured parsing keeps source coordinates: page number, table index, row index, paragraph id, worksheet name and cell range.
- Answers are emitted with `[S#]` markers resolved against a budget ledger; unresolved citations are rejected before display.

**Hybrid retrieval without a vector service**
- BM25 and character n-gram hashed vectors are ranked independently and fused with Reciprocal Rank Fusion (RRF).
- Falls back to exact NumPy similarity when FAISS is unavailable — no silent failure, the degradation is reported in the UI.

**Context budgeting**
- Byte-level budget accounting per request; complete table rows are never split to fit the budget.
- Rows exceeding the remaining budget are skipped rather than truncated, and the decision is logged.

**Privacy and isolation**
- AES-GCM reversible masking with Scrypt (n=2^15, r=8, p=1) key derivation and AAD binding; residual-value scan after masking; unknown tokens block restoration instead of leaking ciphertext.
- Per-account workspace isolation; cross-tenant access returns 403/404 rather than an empty result.
- Optional execution sandbox: no network, no mounts, read-only root, non-root user, 0.5 CPU / 128 MiB / 12 s.

## Architecture

```
 ingest.py                 engine.py                      local_model.py
┌──────────────────┐   ┌────────────────────────┐   ┌────────────────────┐
│ PDF / DOCX       │   │ BM25  ─┐               │   │ Ollama /api/chat   │
│ XLSX / CSV / MD  │──▶│ n-gram ─┴─▶ RRF ─▶ top-k│──▶│ /api/embed         │
│ → Unit[]         │   │ context budget ledger  │   │ (localhost only)   │
└──────────────────┘   └────────────────────────┘   └────────────────────┘
        │                         │                          │
        └───────────┬─────────────┴──────────────┬───────────┘
                    ▼                            ▼
              studio/api.py                 app.py / cli.py
        FastAPI: workspace, masking,     Streamlit UI + CLI
        sandbox runner, rerank           (same parsing & QA core)
```

## Quick start

Requires Python 3.11+ and a local [Ollama](https://ollama.com/) instance for generation (retrieval-only mode works without one).

```bash
python -m pip install -r requirements-tested.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

CLI, retrieval-only:

```bash
python cli.py examples/spec.pdf -q "What is BETA pressure?"
python cli.py examples/spec.pdf -q "What is BETA pressure?" --model qwen3:30b-a3b
```

Run the regression suite:

```bash
python -m ruff check .
python -m pytest -q
python demo.py --report evaluation.json
```

## Evaluation

`demo.py --report` produces `evaluation.json` over a 6-question labelled set built on synthetic sample documents:

| Retriever | Hit@1 | Hit@3 |
| --- | --- | --- |
| keyword (BM25) | 1.00 | 1.00 |
| vector (character n-gram) | 1.00 | 1.00 |
| hybrid (RRF) | 1.00 | 1.00 |

**Read this honestly:** six synthetic questions is a smoke test, not a benchmark. It verifies that the citation path is wired correctly and that hybrid fusion does not degrade keyword recall. A blind test on real, messy documents is the next milestone — see *Limitations*.

Regression: `pytest` 22 passed. Acceptance scripts in `tools/` cover permission, encryption, and sandbox boundaries (11 checks).

## Limitations

Declared up front, because they define the scope of any claim made about this project:

- **No OCR.** Scanned PDFs without a text layer are reported, not silently mis-parsed.
- **No nested tables or merged-cell inference.** Complex layouts degrade to paragraph-level evidence.
- **Blind test pending.** Retrieval quality on real documents has not yet been measured; all published numbers are on synthetic data.
- **Single-node, single-tenant scale.** Workspace isolation is enforced at the application layer, not by a database cluster.
- **Local models only.** No cloud provider adapters by design.

## Repository layout

```
app.py            Streamlit UI
cli.py            command-line entry point
engine.py         hybrid retrieval, RRF fusion, context budget
ingest.py         PDF / OOXML / CSV parsing into coordinate-aware units
local_model.py    Ollama client (localhost, no proxy, no redirects)
studio/           FastAPI service: api, store, privacy, rerank, sandbox runner
tests/            regression suite
tools/            acceptance scripts (permission / encryption / sandbox)
examples/         synthetic sample documents
deploy/           Docker Compose reference deployment
```

## Background

Built as an individual engineering project. The author owns the architecture, acceptance criteria, test design, and integration work; portions of the early implementation were produced with AI pair-programming and reviewed line by line. This is stated explicitly so that reviewers can weigh the code accordingly — the verifiable part is the design and the acceptance evidence, not the keystroke count.

## License

MIT — see [LICENSE](LICENSE).
