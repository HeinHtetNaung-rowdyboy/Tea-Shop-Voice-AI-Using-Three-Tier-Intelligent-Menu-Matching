# Myanmar Raj-0 + 3-tier menu matching integration

This archive upgrades the **uploaded Streamlit + FastAPI app**, preserves its 156-item POS catalog and existing kitchen order endpoints, and adds these files under `app/`:

- `myanmar_text_normalizer.py` — conservative Burmese cleanup, trailing filler removal.
- `menu_matcher.py` — exact aliases and RapidFuzz suggestions.
- `semantic_matcher.py` — optional lazy-loaded FAISS, embeddings with `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
- `order_parser.py` — item span parsing, numbers, quantities, warnings, and candidates.

## Windows installation

From the project folder:

```bat
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Optional Tier 3:

```bat
pip install -r requirements-semantic.txt
```

Copy `.env.example` to `.env` if needed, then set your Raj URL and **a nonempty API_KEY for remote deployments**. Set `ENABLE_SEMANTIC=true` when ready to run Tier 3. The first query needing Tier 3 downloads the embedding model; subsequent queries reuse the model in memory. Enable only with enough RAM, particularly on Z.com C2.

Run FastAPI and Streamlit in separate CMD windows:

```bat
venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
venv\Scripts\python.exe -m streamlit run streamlit_app.py
```

The `/api/parse` route returns the **full reviewable result**, including `items`, `candidates`, `warnings`, `unmatched_text`, `normalized_text`, and `semantic_error`. The Streamlit UI provides per-item quantity and menu selection, plus approval before adding suggestions to the cart. The API still validates all submitted item IDs and calculates authoritative prices from the menu.

**Notes**: The parser is an initial integration, not a proven production-grade speech-language model. Ambiguous `ခွဲ` is not rewritten to `ခွက်`. If input contains unrecognized words, review them; semantic scores are not confidence probabilities. POS item `unit_needs_review` metadata is retained, so confirm menu units. Benchmark with real waiter recordings before production. Use HTTPS and authenticated access in production; never expose Raj API or the Streamlit dashboard without suitable network controls. Do not copy your original `.env` or orders database into a shared artifact.
