
"""Raj-0 NeMo-Speech.cpp HTTP transcription API client.

Receives waiter WAV audio, calls the remote Raj-0 server,
and normalizes the returned Myanmar transcription.
"""

import io
import os
import wave

import requests

from .config import raj_url
from .myanmar_text_normalizer import normalize_text


class RajError(RuntimeError):
    """Raised when the Raj-0 API returns an error."""
    pass


def validate_wav(content: bytes, max_mb: int = 10) -> float:
    """Validate PCM16/PCM32 WAV and return audio duration."""

    if not content or len(content) > max_mb * 1024 * 1024:
        raise ValueError(
            f"Audio must be WAV and no larger than {max_mb} MB"
        )

    try:
        with wave.open(io.BytesIO(content), "rb") as wav:
            if wav.getcomptype() != "NONE":
                raise ValueError("Use uncompressed PCM WAV")

            if wav.getnchannels() not in (1, 2):
                raise ValueError("Use mono or stereo WAV audio")

            if wav.getsampwidth() not in (2, 4):
                raise ValueError("Use PCM16 or PCM32 WAV")

            sample_rate = wav.getframerate()

            if sample_rate <= 0:
                raise ValueError("Invalid audio sample rate")

            duration = wav.getnframes() / sample_rate

            if not 0.25 <= duration <= 60:
                raise ValueError(
                    "Recording must be 0.25–60 seconds"
                )

            return duration

    except (wave.Error, EOFError) as exc:
        raise ValueError(
            "Invalid WAV recording; try Streamlit microphone again"
        ) from exc


def _headers() -> dict:
    """Build Raj API authentication headers."""

    headers = {}

    api_key = os.getenv("RAJ_API_KEY", "").strip()

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return headers


def _request_session() -> requests.Session:
    """Return HTTP session.

    Set RAJ_TRUST_ENV=false only when connecting directly
    and environment proxies should be ignored.
    """

    session = requests.Session()

    session.trust_env = (
        os.getenv("RAJ_TRUST_ENV", "true").lower()
        in ("true", "1", "yes")
    )

    return session


def transcribe_wav(content: bytes) -> str:
    """Transcribe WAV audio and normalize Myanmar text."""

    max_mb = int(os.getenv("MAX_AUDIO_MB", "10"))

    validate_wav(content, max_mb)

    connect_timeout = float(
        os.getenv("RAJ_CONNECT_TIMEOUT", "15")
    )

    read_timeout = float(
        os.getenv("RAJ_TIMEOUT_SECONDS", "120")
    )

    url = f"{raj_url().rstrip('/')}/v1/audio/transcriptions"

    try:
        with _request_session() as session:
            response = session.post(
                url,
                headers=_headers(),
                files={
                    "file": (
                        "waiter.wav",
                        content,
                        "audio/wav"
                    )
                },
                data={
                    "language": "my-MM",
                    "response_format": "json",
                    "verbatim": "true",
                    "automatic_punctuation": "false"
                },
                timeout=(connect_timeout, read_timeout),
            )

            response.raise_for_status()

            result = response.json()

        if not isinstance(result, dict):
            raise RajError("Raj API returned invalid JSON")

        raw_text = result.get("text", "")

        if not isinstance(raw_text, str):
            raise RajError(
                "Raj API response has no valid text"
            )

        # Remove Raj metadata and apply verified
        # Myanmar corrections and filler removal.
        clean_text = normalize_text(raw_text)

        if not clean_text:
            raise RajError(
                "Raj-0 returned an empty transcription"
            )

        return clean_text

    except requests.exceptions.ConnectTimeout as exc:
        raise RajError(
            f"Connection timed out: {raj_url()}. "
            "Check the Linux Raj server and network."
        ) from exc

    except requests.exceptions.ReadTimeout as exc:
        raise RajError(
            "Raj-0 transcription timed out. "
            "The remote ASR server may be busy."
        ) from exc

    except requests.exceptions.ConnectionError as exc:
        raise RajError(
            f"Cannot connect to Raj-0 at {raj_url()}. "
            "Check server, port and firewall."
        ) from exc

    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code

        raise RajError(
            f"Raj-0 returned HTTP {status}. "
            "Check API authentication and model readiness."
        ) from exc

    except requests.exceptions.RequestException as exc:
        raise RajError(
            f"Raj-0 API request failed: {exc}"
        ) from exc

    except (ValueError, TypeError) as exc:
        raise RajError(
            f"Invalid response from Raj-0: {exc}"
        ) from exc


def check_raj() -> dict:
    """Check whether the remote Raj model is ready."""

    url = f"{raj_url().rstrip('/')}/ready"

    try:
        with _request_session() as session:
            response = session.get(
                url,
                headers=_headers(),
                timeout=(
                    float(
                        os.getenv("RAJ_CONNECT_TIMEOUT", "15")
                    ),
                    10,
                ),
            )

            response.raise_for_status()

            result = response.json()

        if not isinstance(result, dict):
            return {
                "ready": False,
                "error": "Unexpected Raj readiness response"
            }

        return result

    except (requests.RequestException, ValueError) as exc:
        return {
            "ready": False,
            "error": str(exc)
        }
