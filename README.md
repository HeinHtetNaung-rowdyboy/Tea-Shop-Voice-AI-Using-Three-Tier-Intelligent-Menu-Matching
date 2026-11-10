# Myanmar Tea Shop Voice AI — Raj-0 Online MVP

Burmese waiter voice → Raj-0 ASR transcription → Myanmar text normalization → **Three-Tier Intelligent Menu Matching (Exact Alias → RapidFuzz → FAISS Semantic Search)** → quantity extraction → waiter confirmation → kitchen order management.

The system uses a Streamlit frontend and FastAPI backend to recognize Myanmar restaurant orders and match them against the existing POS menu catalog. It supports common Raj-0 transcription errors, fuzzy menu-name matching, semantic candidate retrieval, and human verification before kitchen submission.

**No model weights are bundled.** This package connects to a **running Raj-0 server** with the NeMo-Speech.cpp HTTP API. It is not a free hosted ASR subscription and no hosted endpoint is provided.



## 3. Three-Tier Intelligent Menu Matching

The Myanmar Tea Shop Voice AI system uses a three-tier menu matching
architecture to identify restaurant menu items from Raj-0 Burmese
speech transcription.

The three tiers are processed in the following order:

### Tier 1 — Exact Alias Matching

Tier 1 compares the normalized ASR transcription against official
POS menu names and predefined aliases stored in `data/menu.json`.

It supports verified alternative spellings and common Raj-0
transcription errors.

For example:

- Spoken item: `နံပြားကြက်ဥကပ်ကြော်`
- Raj-0 transcription: `နံပြား ကြောက်ကပ်ကြုံ`
- Matched menu item: `ITEM162 — နံပြားကြက်ဥကပ်ကြော်`
- Matching method: `exact`
- Similarity score: `1.0`

When a unique exact alias is found, Tier 2 and Tier 3 are skipped.
Aliases shared by multiple POS items require waiter confirmation.

### Tier 2 — Fuzzy String Matching (RapidFuzz)

If Tier 1 cannot identify the menu item, Tier 2 uses RapidFuzz
to compare the recognized Burmese phrase against menu names
and aliases.

RapidFuzz calculates character-string similarity and ranks
potential matching menu items.

Example from a Raj-0 transcription test:

- ASR text: `နံပြား ထောပတ်တုံး တစ်ဝဲပေးပါ`
- Highest fuzzy candidate: `ITEM163 — နံပြားထောပတ်သုပ်`
- Fuzzy similarity: `66.67%`

The Streamlit application displays the highest fuzzy similarity,
the top matching candidates, and their POS item IDs.

Fuzzy similarity is NOT a probability that a menu item is correct.
Uncertain candidates require waiter confirmation.

### Tier 3 — Semantic Matching (FAISS + Multilingual MiniLM)

When exact matching fails and fuzzy matching is insufficient,
the system can use semantic vector search.

The optional semantic retrieval component uses:

- Sentence Transformers
- `paraphrase-multilingual-MiniLM-L12-v2`
- 384-dimensional text embeddings
- FAISS similarity search

Menu names and aliases are converted into embeddings.
The recognized Burmese phrase is encoded using the same model,
and FAISS retrieves similar menu candidates.

Semantic matching can help identify differently worded menu
phrases, but it cannot reliably repair completely incorrect
ASR transcription.

FAISS similarity scores are not calibrated confidence
probabilities and must not be directly compared with
RapidFuzz percentages.

Semantic search can be enabled in `.env`:

```ini
ENABLE_SEMANTIC=true
SEMANTIC_MODEL_ID=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Install the optional dependencies:

```cmd
pip install -r requirements-semantic.txt
```

The MiniLM model is downloaded separately and is not bundled
with this project.

If the semantic model is unavailable, the system preserves
available exact and fuzzy matching results.

### Three-Tier Matching Workflow

```text
Waiter speaks Myanmar
        |
        v
Raj-0 Speech Recognition
        |
        v
Myanmar Text Normalization
        |
        v
Menu Phrase and Quantity Extraction
        |
        v
Tier 1: Exact Alias Matching
        |
        | No exact match
        v
Tier 2: RapidFuzz Matching
        |
        | Insufficient fuzzy result
        v
Tier 3: FAISS Semantic Search (Optional)
        |
        v
Candidate Menu Items
        |
        v
Waiter Verifies Item and Quantity
        |
        v
Add to Cart
        |
        v
Confirm Order and Send to Kitchen
```

### Python Modules

| Module | Responsibility |
|---|---|
| `app/raj_client.py` | Remote Raj-0 ASR API integration |
| `app/myanmar_text_normalizer.py` | Burmese text normalization and verified corrections |
| `app/menu_matcher.py` | Tier 1 exact aliases and Tier 2 RapidFuzz |
| `app/semantic_matcher.py` | Tier 3 multilingual MiniLM + FAISS |
| `app/order_parser.py` | Menu phrase detection, quantities and candidate review |
| `api.py` | FastAPI endpoints and matching diagnostics |
| `streamlit_app.py` | Voice interface, matching scores and waiter confirmation |
| `data/menu.json` | POS menu catalog, aliases, prices and item IDs |

### Matching Diagnostics

The FastAPI application can log the matching stages used for
each recognized order.

Example:

```text
[TIER 1] No exact alias match
[TIER 2] Starting RapidFuzz search
[TIER 2] ITEM163 | နံပြားထောပတ်သုပ် | 66.67%
[TIER 3] Starting FAISS search
[MATCH] Tiers attempted: ['exact', 'fuzzy', 'semantic']
[MATCH] Final status: needs_confirmation
```

The Streamlit interface displays candidate menu items and
similarity scores for waiter review.

The system never automatically sends an uncertain AI-suggested
menu item to the kitchen. The waiter must verify the selected
product and quantity before adding it to the order.


## 0. Requirements

- For Windows UI and API: Python **3.11**, VS Code or Windows CMD; internet access to a running Raj-0 server.
- For Raj-0 native inference: Linux server (Ubuntu recommended), Git, C++ compiler, `cmake >=3.26`, Ninja, ~1 GB model download plus build storage. CPU works but speed varies by host; GPU may be preferable for high-volume use.
- Streamlit microphone requires browser mic permission. Publicly hosted browsers need **HTTPS** for reliable mic access. Running on `localhost` works without HTTPS in most browsers.
- The native Raj-0 inference setup has not been built by this package; consult the author's current instructions for compatibility.

## 1. Extract and configure (Windows)

Open the extracted `raj0-teashop-online` folder in VS Code. Open terminal **CMD** (not PowerShell) and run:

```cmd
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`:

```ini
APP_PASSWORD=YOUR_STRONG_UI_PASSWORD
API_KEY=YOUR_DIFFERENT_LONG_RANDOM_API_KEY
RAJ_API_URL=http://127.0.0.1:8080
RAJ_API_KEY=YOUR_RAJ_SERVER_API_KEY_IF_ENABLED
BACKEND_API_URL=http://127.0.0.1:8000
```

### Terminal 1 — API

```cmd
.venv\Scripts\activate
uvicorn api:app --host 127.0.0.1 --port 8000
```

### Terminal 2 — Streamlit

```cmd
.venv\Scripts\activate
streamlit run streamlit_app.py
```

Open `http://localhost:8501`, sign in with `APP_PASSWORD`. Go to **Status** to check Raj-0. The **sample text** button and text order extraction work before Raj-0 is installed (test the order flow first). The actual microphone transcription requires the Raj-0 server.

## 2. Start a Raj-0 server on Ubuntu Linux / WSL2

The author's reference process uses `raj-0-q8_0.gguf` and a patched version of `NeMo-Speech.cpp` with version-pinned sources. The included script follows those instructions but **has not been end-to-end verified in this environment**.

On Ubuntu, install tools:

```bash
sudo apt update
sudo apt install -y git build-essential python3-venv python3-pip curl
bash scripts/install_raj0_linux.sh
```

If using WSL2, copy `scripts/install_raj0_linux.sh` into Ubuntu or access it from `/mnt/c/...`. The script uses model author's commit and patch; check the upstream docs if it fails.

Start the native server (replace password):

```bash
cd ~/raj0-runtime/NeMo-Speech.cpp
export NEMO_SPEECH_HTTP_API_KEY='REPLACE_WITH_A_LONG_SECRET'
build/cpu-asr/bin/nemo-speech serve \
  --host 127.0.0.1 --port 8080 --device cpu \
  --asr-model "$HOME/raj0-runtime/model/raj-0-q8_0.gguf" \
  --asr.model.name Raj-0-Q8 \
  --asr.streaming.rnnt_right_context 3 --threads 2
```

Test from that SAME Ubuntu machine using a real WAV (`test.wav`):

```bash
curl -X POST http://127.0.0.1:8080/v1/audio/transcriptions \
  -H 'Authorization: Bearer REPLACE_WITH_A_LONG_SECRET' \
  -F file=@test.wav -F language=my-MM \
  -F automatic_punctuation=false -F verbatim=true -F response_format=json
```

Expected successful JSON includes `"text": "..."`. This is **real Raj-0 inference**, not a text demonstration. If running Raj in WSL2 and UI in Windows, use WSL's reachable host address and port configuration; `localhost` forwarding is often available but not guaranteed in every WSL setup.

Upstream instructions: https://huggingface.co/aungzaythant/Raj-0/blob/main/INFERENCE.md

## 3. Online deployment: two practical choices

### Option A — Single Linux VPS/cloud VM, recommended first

Run Raj-0 natively on the SAME server, bound to `127.0.0.1:8080` (never open this unauthenticated port to the internet). Install Docker Engine + Compose on the same server for UI/API:

```bash
cp .env.example .env
# Edit .env: APP_PASSWORD, API_KEY, RAJ_API_KEY, RAJ_API_URL
# Note: Raj listens on the HOST, but Docker's API lives in a container.
# Linux Docker: RAJ_API_URL=http://host.docker.internal:8080 requires host-gateway mapping
sudo docker compose up -d --build
```

To allow container→Raj reachability on Linux, add `extra_hosts: ["host.docker.internal:host-gateway"]` under the **api** service in `docker-compose.yml`, and configure Raj to bind to a private host interface reachable from Docker **rather than** host `127.0.0.1`. Binding Raj to a nonloopback interface requires firewall restrictions; it must not be publicly reachable. Or run FastAPI natively on host alongside Raj and use Docker only for Streamlit.

**Simplest proven wiring design:** run all 3 processes (Raj, API, Streamlit) directly on the SAME Linux VM; then `.env` uses `http://127.0.0.1:8080` and `http://127.0.0.1:8000` with no container network changes. Put a TLS reverse proxy in front of Streamlit port 8501 (e.g., Caddy or Nginx), and do not expose FastAPI or Raj publicly.

Example Caddyfile (replace domain):

```caddyfile
orders.example.com {
  reverse_proxy 127.0.0.1:8501
}
```

Point your domain DNS record to the VM, open only ports 80 and 443 externally, configure TLS, secure the VM, and set `APP_PASSWORD` and `API_KEY` to different strong secrets. Never store API keys in Flutter source or a browser app. For real production operations, use proper individual user accounts, TLS, backups, and server-side role authorization. The shared-password UI is an MVP, not enterprise-grade authentication.

### Option B — Separate remote Raj-0 server

Host Raj-0 on a second Linux instance (or a provider offering a compatible Raj-0 transcription endpoint). Set:

```ini
RAJ_API_URL=https://raj.example.com
RAJ_API_KEY=SERVER_SECRET
```

Restrict access with TLS + authentication + network policy. Configure API with this address; Streamlit only contacts FastAPI and never accesses Raj credentials directly. This makes a Flutter frontend easier later.

**Caution:** No official public always-on Raj-0 API endpoint is assumed; the Hugging Face model page is weights/documentation, not a guaranteed hosted endpoint.

## 4. Test step by step

1. Start FastAPI and Streamlit; sign in to UI.
2. Use **နမူနာ စာသားထည့်ရန်** (sample text), then **စာသားမှ အော်ဒါထုတ်ရန်**.
3. Confirm the cart shows `လက်ဖက်ရည် × 2 = 3,000 Ks`, `ပလာတာ × 3 = 6,000 Ks`, total 9,000 Ks.
4. Submit to kitchen and open Kitchen screen to change ticket status.
5. Start Raj-0; verify `/ready` and test a sample WAV using curl on its server.
6. Record a real waiter order through Streamlit microphone and click **Raj-0 ဖြင့် စာသားပြောင်းရန်**.
7. Correct the transcription if needed, parse and confirm; the UI never auto-submits an unverified order.
8. Run automated tests: `pytest -q` (these **mock** ASR network responses; they do **not** prove real Raj-0 accuracy).

## 5. Flutter API contract

- `POST /api/asr` multipart `file` (WAV, max 10 MB, duration 0.25–60s) → `{ "text": "...", "model": "Raj-0" }`
- `POST /api/parse` JSON `{ "text": "..." }` → `{ "items": [...] }`
- `GET /api/menu` → list
- `POST /api/orders` JSON `{ "table_no": "Table 1", "waiter": "...", "transcript": "...", "items": [{"id":"tea","qty":2}] }` → `{ "id": 1 }`
- `GET /api/orders` → list
- `PATCH /api/orders/{id}/status` JSON `{ "status": "preparing" }`

All `/api/*` calls require request header `X-API-Key: YOUR_API_KEY` in this MVP. **Do not embed a shared secret inside a distributed Flutter APK**; add mobile authentication (short-lived tokens/roles) before rollout. Example endpoint docs available at `http://127.0.0.1:8000/docs` locally.

## 6. Customization and limits

- `data/menu.json`: item names, aliases and prices (MMK).
- `app/ordering.py`: Burmese quantity recognition and special instructions.
- `app/raj_client.py`: Raj server API client.
- `streamlit_app.py`: dark waiter screen and kitchen management.
- `api.py`: API for Flutter integration.
- SQLite stores orders in `data/orders.db`, not intended for large multi-store production; use PostgreSQL and migrations later.
- ASR accuracy is affected by room noise, dialects, and accent. Every recognized order must be checked by the waiter.
- No real-time streaming in this MVP: waiters record a short clip, then transcribe.
- No offline mobile support in this first online version.

## Model & licensing

Raj-0 official model: https://huggingface.co/aungzaythant/Raj-0

Raj-0's repo currently labels its license `apache-2.0` (relicensed after earlier `raj-0-noncommercial` versions). Confirm the license and NOTICE from the exact model revision before commercial deployment. This project **does not bundle or redistribute** Raj-0 model weights or source from NeMo-Speech.cpp.
