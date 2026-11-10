
"""Myanmar Tea Shop Voice API with three-tier matching diagnostics."""

import logging
import os
import secrets
from functools import lru_cache

from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile,
)
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.ordering import (
    init_db,
    list_orders,
    menu,
    save_order,
    update_status,
)
from app.order_parser import OrderParser
from app.raj_client import (
    RajError,
    check_raj,
    transcribe_wav,
)


# ==========================================
# LOGGING CONFIGURATION
# ==========================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logger = logging.getLogger("voice_order")
logger.setLevel(
    getattr(logging, LOG_LEVEL, logging.INFO)
)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        )
    )
    logger.addHandler(handler)

logger.propagate = False

# Only enable transcript logging during
# protected development/testing.
VOICE_DEBUG = (
    os.getenv("VOICE_DEBUG", "false")
    .strip()
    .lower()
    in {"true", "1", "yes"}
)


# ==========================================
# FASTAPI INITIALIZATION
# ==========================================

app = FastAPI(
    title="Myanmar Tea Shop Voice API",
    version="1.1.0",
)

init_db()


# ==========================================
# API AUTHENTICATION
# ==========================================

def authorize(
    x_api_key: str | None = Header(default=None)
):
    expected = os.getenv("API_KEY", "").strip()

    if not expected:
        # Local-development compatibility only.
        # Production deployments must set API_KEY.
        return True

    if not x_api_key or not secrets.compare_digest(
        x_api_key,
        expected,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )

    return True


# ==========================================
# REQUEST MODELS
# ==========================================

class ParseInput(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=2000,
    )


class OrderInput(BaseModel):
    table_no: str = Field(
        min_length=1,
        max_length=32,
    )

    waiter: str = Field(
        default="Waiter",
        max_length=80,
    )

    transcript: str = Field(
        default="",
        max_length=2000,
    )

    items: list[dict]


class StatusInput(BaseModel):
    status: str


# ==========================================
# PARSER CONFIGURATION
# ==========================================

def semantic_is_enabled() -> bool:
    return (
        os.getenv("ENABLE_SEMANTIC", "false")
        .strip()
        .lower()
        in {"true", "1", "yes"}
    )


@lru_cache(maxsize=2)
def parser_for_mode(enabled: bool):
    # Reuse the parser and cached semantic matcher.
    return OrderParser(enable_semantic=enabled)


# ==========================================
# HEALTH CHECK
# ==========================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "teashop-api",
    }


# ==========================================
# RAJ-0 READINESS
# ==========================================

@app.get(
    "/api/raj-status",
    dependencies=[Depends(authorize)],
)
def raj_status():
    return check_raj()


# ==========================================
# MENU
# ==========================================

@app.get(
    "/api/menu",
    dependencies=[Depends(authorize)],
)
def get_menu():
    return menu()


# ==========================================
# THREE-TIER ORDER PARSING
# ==========================================

@app.post(
    "/api/parse",
    dependencies=[Depends(authorize)],
)
def parse(body: ParseInput):

    enabled = semantic_is_enabled()

    logger.info(
        "[PARSE] Semantic tier enabled: %s",
        enabled,
    )

    if VOICE_DEBUG:
        logger.info(
            "[PARSE] Input transcription: %r",
            body.text,
        )

    parser = parser_for_mode(enabled)

    result = parser.parse(body.text)

    logger.info(
        "[PARSE] Order lines: %s; "
        "confirmation required: %s",
        len(result.get("items", [])),
        result.get("requires_confirmation"),
    )

    logger.info(
        "[PARSE] Tiers attempted: %s",
        result.get(
            "tiers_attempted",
            "not supplied by parser",
        ),
    )

    for index, item in enumerate(
        result.get("items", []),
        start=1,
    ):
        logger.info(
            "[PARSE] Line %d: "
            "ID=%s tier=%s method=%s qty=%s review=%s",
            index,
            item.get("id"),
            item.get("match_tier"),
            item.get("match_method"),
            item.get("qty"),
            item.get("needs_review"),
        )

        if VOICE_DEBUG:
            logger.info(
                "[PARSE] Line %d phrase=%r warnings=%s",
                index,
                item.get("phrase"),
                item.get("warnings"),
            )

            for candidate in item.get(
                "candidates", []
            ):
                logger.info(
                    "[CANDIDATE] "
                    "%s | %s | %s | score=%s",
                    candidate.get("id"),
                    candidate.get("name"),
                    candidate.get("method"),
                    candidate.get("score"),
                )

    if result.get("semantic_error"):
        logger.warning(
            "[TIER 3] FAISS issue: %s",
            result["semantic_error"],
        )

    return result


# ==========================================
# RAJ-0 SPEECH TO TEXT
# ==========================================

@app.post(
    "/api/asr",
    dependencies=[Depends(authorize)],
)
async def asr(file: UploadFile = File(...)):

    allowed_types = {
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "application/octet-stream",
    }

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail="Please submit a WAV recording",
        )

    limit = (
        int(os.getenv("MAX_AUDIO_MB", "10"))
        * 1024
        * 1024
    )

    data = await file.read(limit + 1)

    if len(data) > limit:
        raise HTTPException(
            status_code=413,
            detail="Audio too large",
        )

    try:
        # Raj client uses blocking requests.
        # Run it in a worker thread.
        text = await run_in_threadpool(
            transcribe_wav,
            data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RajError as exc:
        logger.error(
            "[ASR] Raj-0 request failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    if VOICE_DEBUG:
        logger.info(
            "[ASR] Normalized Raj-0 transcript: %r",
            text,
        )
    else:
        logger.info(
            "[ASR] Transcription completed"
        )

    return {
        "text": text,
        "model": "Raj-0",
    }


# ==========================================
# LIST ORDERS
# ==========================================

@app.get(
    "/api/orders",
    dependencies=[Depends(authorize)],
)
def orders():
    return list_orders()


# ==========================================
# SAVE ORDER
# ==========================================

@app.post(
    "/api/orders",
    dependencies=[Depends(authorize)],
)
def create_order(body: OrderInput):

    try:
        order_id = save_order(
            body.table_no,
            body.waiter,
            body.transcript,
            body.items,
        )

        return {"id": order_id}

    except (
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ==========================================
# UPDATE KITCHEN ORDER STATUS
# ==========================================

@app.patch(
    "/api/orders/{order_id}/status",
    dependencies=[Depends(authorize)],
)
def status(order_id: int, body: StatusInput):

    try:
        update_status(
            order_id,
            body.status,
        )

        return {"ok": True}

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
