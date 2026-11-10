import json
import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv

# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

st.set_page_config(
    page_title="စားပွဲ အော်ဒါ | Raj-0",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
html,body,[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#050505;color:#f1f1f1}
.block-container{max-width:1100px;padding-top:1.3rem}
h1,h2,h3,p,label{font-family:Arial,"Noto Sans Myanmar",sans-serif}
[data-testid="stAudioInput"]{background:#06191b;border:1px solid #123236;border-radius:20px;padding:16px}
[data-testid="stAudioInput"] button{border-radius:50%}
.stButton>button[kind="primary"]{background:#00282a;border:1px solid #063b3e;color:white;font-weight:700;min-height:56px;border-radius:12px}
[data-testid="stTextArea"] textarea{background:#303030;color:white;border:0;border-radius:11px;font-size:19px}
[data-testid="stMetricValue"]{color:#f6f6f6}
hr{border-color:#222}
</style>
""",
    unsafe_allow_html=True,
)

API_BASE = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.getenv("API_KEY", "").strip()

# LOCAL DEVELOPMENT ONLY: no Streamlit login.
# IMPORTANT: This does not disable FastAPI authentication.
# Do not expose this unauthenticated UI to the public internet.


def api(method: str, path: str, **kwargs):
    """Call FastAPI. The backend handles parsing, orders, and Raj-0."""
    headers = dict(kwargs.pop("headers", {}))
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    try:
        response = requests.request(
            method, API_BASE + path, headers=headers, timeout=125, **kwargs
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)
        if exc.response is not None:
            try:
                payload = exc.response.json()
                detail = payload.get("detail", detail) if isinstance(payload, dict) else detail
            except ValueError:
                pass
        raise RuntimeError(str(detail)) from exc
    except ValueError as exc:
        raise RuntimeError("Backend returned invalid JSON.") from exc


for key, default in {
    "cart": [],
    "transcript": "",
    "table": "စားပွဲ 01",
    "waiter": "Waiter 1",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.sidebar.header("🫖 Raj-0 Voice POS")
mode = st.sidebar.radio(
    "Screen", ["🎙️ အော်ဒါတင်ရန်", "🍳 မီးဖိုချောင်", "📋 Menu", "⚙️ Status"]
)
st.sidebar.caption("Local development mode: Streamlit login disabled")

if mode == "🎙️ အော်ဒါတင်ရန်":
    col_l, col_r = st.columns([4, 1])
    with col_l:
        st.markdown("### စားပွဲနံပါတ်")
    with col_r:
        st.selectbox(
            "Table",
            [f"စားပွဲ {i:02d}" for i in range(1, 31)],
            key="table",
            label_visibility="collapsed",
        )

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
    middle = st.columns([1, 2.6, 1])[1]
    with middle:
        st.markdown(
            '<div style="text-align:center"><h2>🎙️</h2>'
            '<h2>အသံဖြင့် အော်ဒါမှာရန်</h2>'
            '<div style="color:#aaa">Tap to record waiter voice</div></div>',
            unsafe_allow_html=True,
        )
        audio = st.audio_input(
            "Record Myanmar waiter voice",
            sample_rate=16000,
            label_visibility="collapsed",
        )
        if st.button(
            "🎧 Raj-0 ဖြင့် စာသားပြောင်းရန်",
            type="primary",
            width="stretch",
            disabled=audio is None,
        ):
            with st.spinner("Raj-0 is recognizing Myanmar speech..."):
                try:
                    result = api(
                        "POST",
                        "/api/asr",
                        files={"file": ("waiter.wav", audio.getvalue(), "audio/wav")},
                    )
                    text = result.get("text", "")
                    if not isinstance(text, str) or not text.strip():
                        st.warning("Raj-0 returned no recognized text. Please record again.")
                    else:
                        st.session_state.transcript = text
                        # Clear previous suggestions so they cannot be mistaken
                        # for matches from the new recording.
                        st.session_state.pending_parse = None
                        st.success("အသံမှ စာသားပြောင်းပြီးပါပြီ")

                        # Automatically invoke all applicable matching tiers.
                        with st.spinner("Matching menu items (exact / fuzzy / FAISS)..."):
                            try:
                                parsed = api(
                                    "POST",
                                    "/api/parse",
                                    json={"text": text},
                                )
                                st.session_state.pending_parse = parsed
                                st.success(
                                    f"Matching complete: {len(parsed.get('items', []))} "
                                    "item line(s) require review."
                                )
                            except RuntimeError as exc:
                                st.error(
                                    f"ASR succeeded but menu parsing failed: {exc}"
                                )
                except RuntimeError as exc:
                    st.error(f"ASR connection problem: {exc}")

    st.divider()
    st.markdown("**အသံမှ စာသားသို့**")
    st.text_area(
        "Recognized text — edit before extracting",
        key="transcript",
        height=90,
        label_visibility="collapsed",
        placeholder="လက်ဖက်ရည် နှစ်ခွက် ပလာတာ သုံးပွဲ",
    )

    a, b = st.columns([1, 1])
    with a:
        if st.button("🧠 စာသားမှ အော်ဒါထုတ်ရန်", width="stretch"):
            if not st.session_state.transcript.strip():
                st.warning("Please record or type an order.")
            else:
                try:
                    st.session_state.pending_parse = None
                    parsed = api("POST", "/api/parse", json={"text": st.session_state.transcript})
                    st.session_state.pending_parse = parsed
                    if parsed.get("items"):
                        st.info(f"{len(parsed['items'])} candidate item(s). Review before adding to cart.")
                    else:
                        st.warning("No confirmed menu items. Choose from suggestions or add manually.")
                except (RuntimeError, KeyError, TypeError, ValueError) as exc:
                    st.error(f"Could not parse order: {exc}")
    with b:
        if st.button("🧪 နမူနာ စာသားထည့်ရန်", width="stretch"):
            st.session_state.transcript = "လက်ဖက်ရည် နှစ်ခွက် ပလာတာ သုံးပွဲ"
            st.rerun()

    try:
        catalog = api("GET", "/api/menu")
    except RuntimeError as exc:
        st.error(f"Backend not reachable: {exc}")
        catalog = []

    if catalog:
        with st.expander("➕ စားစရာ ထပ်ထည့်ရန် / Add manually"):
            selected = st.selectbox(
                "Menu item",
                catalog,
                format_func=lambda x: f"{x['name']} — {int(x['price']):,} Ks",
            )
            count = st.number_input("Quantity", min_value=1, max_value=99, value=1)
            note = st.text_input("Special instructions")
            if st.button("Add to order"):
                st.session_state.cart.append(
                    {
                        "id": selected["id"],
                        "name": selected["name"],
                        "qty": int(count),
                        "price": int(selected["price"]),
                        "note": note,
                    }
                )
                st.rerun()

    pending = st.session_state.get("pending_parse")
    if pending:
        st.markdown("### 🔎 Three-tier matching review")
        st.caption("Exact → RapidFuzz → optional FAISS (suggestions). No AI suggestion is sent automatically.")
        st.write("**Tiers attempted:**", pending.get("tiers_attempted", "Not provided by parser"))
        with st.expander("🔍 Three-tier diagnostics", expanded=False):
            st.json({
                "tiers_attempted": pending.get("tiers_attempted"),
                "semantic_enabled": pending.get("semantic_enabled"),
                "semantic_error": pending.get("semantic_error"),
                "items": [
                    {
                        "phrase": x.get("phrase"),
                        "match_tier": x.get("match_tier"),
                        "match_method": x.get("match_method"),
                        "tiers_attempted": x.get("tiers_attempted"),
                        "candidates": x.get("candidates", []),
                        "warnings": x.get("warnings", []),
                    }
                    for x in pending.get("items", [])
                ],
            })
        st.text_input("Normalized Burmese", value=pending.get("normalized_text", ""), disabled=True)
        # Highest RapidFuzz match across parsed menu phrases.
        # Fuzzy similarity is a text score, NOT a probability of correctness.
        fuzzy_by_id = {}
        for parsed_line in pending.get("items", []):
            for candidate in parsed_line.get("candidates", []):
                if candidate.get("method") != "fuzzy":
                    continue
                candidate_id = str(candidate.get("id", ""))
                try:
                    score = float(candidate.get("score", 0))
                except (TypeError, ValueError):
                    continue
                if candidate_id and (candidate_id not in fuzzy_by_id or score > fuzzy_by_id[candidate_id]["score"]):
                    fuzzy_by_id[candidate_id] = {
                        "id": candidate_id,
                        "name": candidate.get("name", candidate_id),
                        "score": max(0.0, min(score, 1.0)),
                    }

        ranked_fuzzy = sorted(
            fuzzy_by_id.values(),
            key=lambda candidate: (-candidate["score"], candidate["id"]),
        )
        if ranked_fuzzy:
            best_fuzzy = ranked_fuzzy[0]
            st.markdown("### 🏆 Highest RapidFuzz match")
            item_column, score_column = st.columns([3, 1])
            with item_column:
                st.markdown(f"**{best_fuzzy['name']}**")
                st.caption(f"POS item ID: {best_fuzzy['id']}")
            with score_column:
                st.metric("Fuzzy similarity", f"{best_fuzzy['score'] * 100:.2f}%")
            st.progress(best_fuzzy["score"])
            st.caption("Character similarity only, not AI confidence. Verify the item and quantity before adding to cart.")
            st.dataframe(
                [
                    {
                        "Rank": rank,
                        "Item ID": candidate["id"],
                        "Menu Name": candidate["name"],
                        "Fuzzy Similarity": f"{candidate['score'] * 100:.2f}%",
                    }
                    for rank, candidate in enumerate(ranked_fuzzy[:5], start=1)
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.caption("No Tier 2 fuzzy candidates for this order (an exact match may have returned first).")

        if pending.get("semantic_error"):
            st.warning("Optional FAISS unavailable: " + pending["semantic_error"])
        if pending.get("unmatched_text"):
            st.error("Unmatched speech — review manually: " + " | ".join(pending["unmatched_text"]))
        review_items=[]
        for ix, line in enumerate(pending.get("items", [])):
            options=line.get("candidates", [])
            st.markdown(f"**Spoken phrase {ix+1}:** {line.get('phrase','')}")
            for w in line.get("warnings", []):
                st.caption("⚠️ " + w)
            # List candidates, but also allow any item in complete menu for correction.
            ids=list(dict.fromkeys([c["id"] for c in options] + [c["id"] for c in catalog]))
            by_id={c["id"]:c for c in catalog}
            choices=[item_id for item_id in ids if item_id in by_id]
            if not choices:
                st.warning("No menu candidates available")
                continue
            # Keep per-line fuzzy scores visible alongside candidate choices.
            candidate_scores = {
                str(candidate["id"]): float(candidate["score"])
                for candidate in options
                if candidate.get("method") == "fuzzy"
                and candidate.get("score") is not None
            }
            default_id=line.get("id") or (options[0]["id"] if options else choices[0])
            selected_id=st.selectbox(
                f"Verify menu item #{ix+1}",choices,
                index=choices.index(default_id) if default_id in choices else 0,
                format_func=lambda item_id: (
                    f"{by_id[item_id]['name']} ({int(by_id[item_id]['price']):,} Ks)"
                    + (
                        f" — {candidate_scores[str(item_id)] * 100:.2f}% fuzzy"
                        if str(item_id) in candidate_scores else ""
                    )
                ),
                key=f"candidate_{ix}",
            )
            qty=int(line.get("qty") or 1)
            selected_qty=st.number_input(
                f"Verify quantity #{ix+1}",min_value=1,max_value=99,value=qty,key=f"parsed_qty_{ix}"
            )
            approved=st.checkbox(f"I verified item and quantity #{ix+1}",key=f"confirm_{ix}")
            review_items.append((selected_id,int(selected_qty),approved,line.get("note", "")))
        if st.button("➕ Add verified items to cart",disabled=not review_items or not all(x[2] for x in review_items),width="stretch"):
            for item_id, qty, _, note in review_items:
                item=next(x for x in catalog if x["id"]==item_id)
                st.session_state.cart.append({"id":item["id"],"name":item["name"],
                                              "qty":qty,"price":int(item["price"]),"note":note})
            st.session_state.pending_parse=None
            st.rerun()
        if st.button("Discard parsing suggestions"):
            st.session_state.pending_parse=None
            st.rerun()

    st.divider()
    cart = st.session_state.cart
    for index, item in enumerate(cart):
        c1, c2, c3, c4 = st.columns([5, 1.5, 2, 0.8], vertical_alignment="center")
        c1.markdown(
            f"**{item['name']}**"
            + (f"  · {item['note']}" if item.get("note") else "")
        )
        item["qty"] = int(
            c2.number_input(
                "Qty",
                min_value=1,
                max_value=99,
                value=int(item["qty"]),
                key=f"qty_{index}",
                label_visibility="collapsed",
            )
        )
        c3.markdown(f"**{int(item['price']) * int(item['qty']):,} Ks**")
        if c4.button("✕", key=f"rm_{index}"):
            cart.pop(index)
            st.rerun()

    total = sum(int(x["price"]) * int(x["qty"]) for x in cart)
    st.divider()
    total_left, total_right = st.columns([3, 1])
    total_left.markdown("### စုစုပေါင်း")
    total_right.markdown(f"### {total:,} Ks")
    st.text_input("Waiter name", key="waiter")

    if st.button(
        "✅ အော်ဒါအတည်ပြုရန် / Send to kitchen",
        type="primary",
        width="stretch",
        disabled=not cart,
    ):
        try:
            ticket = api(
                "POST",
                "/api/orders",
                json={
                    "table_no": st.session_state.table,
                    "waiter": st.session_state.waiter,
                    "transcript": st.session_state.transcript,
                    "items": cart,
                },
            )
            st.session_state.cart = []
            st.session_state.transcript = ""
            st.success(f"Kitchen ticket #{ticket['id']} created! Go to Kitchen screen.")
        except (RuntimeError, KeyError) as exc:
            st.error(f"Could not save order: {exc}")

    if cart and st.button("Clear cart"):
        st.session_state.cart = []
        st.rerun()

elif mode == "🍳 မီးဖိုချောင်":
    st.title("🍳 မီးဖိုချောင် / Kitchen")
    if st.button("🔄 Refresh"):
        st.rerun()
    try:
        for order in api("GET", "/api/orders"):
            with st.expander(
                f"#{order['id']} · {order['table_no']} · "
                f"{int(order['total']):,} Ks · {order['status']}"
            ):
                st.caption(f"{order['created_at']} · {order['waiter']}")
                for x in json.loads(order["items_json"]):
                    st.write(f"{x['name']} × {x['qty']} — {x.get('note', '')}")
                statuses = ["new", "preparing", "served"]
                current = order["status"]
                selected = st.selectbox(
                    "Status",
                    statuses,
                    index=statuses.index(current) if current in statuses else 0,
                    key=f"status_{order['id']}",
                )
                if st.button("Update", key=f"update_{order['id']}"):
                    try:
                        api(
                            "PATCH",
                            f"/api/orders/{order['id']}/status",
                            json={"status": selected},
                        )
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(f"Could not update status: {exc}")
    except (RuntimeError, KeyError, ValueError) as exc:
        st.error(str(exc))

elif mode == "📋 Menu":
    st.title("📋 မီနူး / Menu")
    try:
        st.dataframe(api("GET", "/api/menu"), width="stretch", hide_index=True)
    except RuntimeError as exc:
        st.error(str(exc))
    st.caption("Edit data/menu.json on the server and restart the API to customize prices and aliases.")

else:
    st.title("⚙️ System status")
    try:
        health = api("GET", "/api/raj-status")
        st.json(health)
        st.info("A ready: true response is not a substitute for testing a real recording.")
    except RuntimeError as exc:
        st.error(str(exc))
    st.write("Backend:", API_BASE)
