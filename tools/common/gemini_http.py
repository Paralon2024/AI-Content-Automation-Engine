import json
import socket
import urllib.error
import urllib.request
from typing import Any


def post_interaction(
    *,
    api_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: int,
    operation: str,
) -> dict[str, Any]:
    """POST a Gemini Interactions request without blindly retrying paid generations.

    A client-side timeout can happen after the provider accepted a generation.
    The caller must treat that outcome as unknown rather than automatically
    submitting a second potentially billable request.
    """
    request = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_body = response.read()
    except urllib.error.HTTPError as exc:
        details = exc.read(4096).decode("utf-8", errors="replace").strip()
        try:
            error_payload = json.loads(details)
            details = (
                error_payload.get("error", {}).get("message")
                or error_payload.get("message")
                or details
            )
        except (ValueError, AttributeError):
            pass
        raise RuntimeError(
            f"Gemini {operation} request rejected (HTTP {exc.code}): "
            f"{details[:2000] or 'No error details returned'}"
        ) from exc
    except (TimeoutError, socket.timeout) as exc:
        raise RuntimeError(
            f"Gemini {operation} request timed out after {timeout_seconds}s. "
            "The generation outcome is unknown because the provider may have "
            "accepted the request; automatic retry was intentionally skipped "
            "to avoid duplicate billable generations."
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not connect to the Gemini {operation} API: {exc.reason}"
        ) from exc

    try:
        result = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"Gemini {operation} API returned invalid JSON "
            f"({len(raw_body)} response bytes)"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            f"Gemini {operation} API returned an unexpected JSON response type"
        )
    return result
