import os
from typing import Any, Callable, Optional

from dotenv import load_dotenv
from google.genai import Client, errors, types
from pydantic import PrivateAttr

from tools.common.base_model import BaseModelTool
from tools.common.messenger import Messenger

load_dotenv()


class GeminiUsage(BaseModelTool):
    model: str
    prompt_tokens: Optional[int] = None
    thoughts_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class GeminiBase(BaseModelTool):
    _client: Client = PrivateAttr()

    @property
    def client(self) -> Client:
        return self._client

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("❌ GEMINI_API_KEY is not defined in the environment")

        # Use the Google GenAI SDK's built-in retry implementation. This avoids
        # stacking a second fixed-delay retry loop around the SDK's own retries.
        self._client = Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=120_000,
                retry_options=types.HttpRetryOptions(
                    attempts=5,
                    initial_delay=1.0,
                    max_delay=30.0,
                    exp_base=2.0,
                    jitter=1.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )

    def _execute_with_retry(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """
        Executes a Gemini API call using the SDK's bounded exponential backoff.

        The SDK retries transient HTTP errors. Non-retryable errors and exhausted
        retries are logged with their real HTTP status and API message so the
        frontend job stream exposes the cause instead of a generic server error.
        """
        model = kwargs.get("model", "unknown")
        try:
            return func(*args, **kwargs)
        except errors.APIError as exc:
            status = exc.status or "unknown"
            message = exc.message or str(exc)
            Messenger.error(
                f"Gemini API request failed for model '{model}' "
                f"(HTTP {exc.code}, {status}): {message}"
            )
            raise
        except Exception as exc:
            Messenger.error(
                f"Gemini request failed for model '{model}' "
                f"({type(exc).__name__}): {exc}"
            )
            raise

    def _extract_usage(self, response: Any, model_name: str) -> GeminiUsage:
        usage_meta = getattr(response, "usage_metadata", None)
        usage = GeminiUsage(model=model_name)

        if usage_meta:
            usage.prompt_tokens = getattr(usage_meta, "prompt_token_count", None)
            usage.thoughts_tokens = getattr(usage_meta, "thoughts_token_count", None)
            usage.output_tokens = getattr(usage_meta, "candidates_token_count", None)
            usage.total_tokens = getattr(usage_meta, "total_token_count", None)

        if usage.total_tokens is not None:
            Messenger.usage(
                model=usage.model,
                prompt=usage.prompt_tokens or 0,
                thoughts=usage.thoughts_tokens or 0,
                output=usage.output_tokens or 0,
                total=usage.total_tokens,
            )
        return usage
