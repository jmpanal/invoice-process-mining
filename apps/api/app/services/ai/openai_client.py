from __future__ import annotations

import json
import time
from typing import Any

from app.core.config import settings


MISSING_OPENAI_KEY_VALUES = {"", "your_api_key_here", "your_openai_api_key_here", "replace_me", "changeme"}


class OpenAIServiceError(RuntimeError):
    pass


class OpenAIConfigurationError(OpenAIServiceError):
    pass


class OpenAIResponseError(OpenAIServiceError):
    pass


class OpenAIRateLimitError(OpenAIResponseError):
    pass


class OpenAIClient:
    def __init__(self) -> None:
        self.chat_model = settings.openai_chat_model
        self.embedding_model = settings.openai_embedding_model
        self.embedding_dimensions = settings.openai_embedding_dimensions

    def _api_key(self) -> str:
        key = settings.openai_api_key.strip()
        if key.lower() in MISSING_OPENAI_KEY_VALUES:
            raise OpenAIConfigurationError("OPENAI_API_KEY is required for RAG embeddings and AI generation.")
        return key

    def _client(self) -> Any:
        from openai import OpenAI

        return OpenAI(api_key=self._api_key())

    def embed(self, text: str) -> list[float]:
        request: dict[str, Any] = {"model": self.embedding_model, "input": text}
        if self.embedding_model.startswith("text-embedding-3"):
            request["dimensions"] = self.embedding_dimensions
        try:
            response = self._request_with_retry("OpenAI embedding request", lambda: self._client().embeddings.create(**request))
            embedding = [float(value) for value in response.data[0].embedding]
        except OpenAIServiceError:
            raise
        except Exception as exc:
            raise self._request_error("OpenAI embedding request", exc) from exc
        if len(embedding) != self.embedding_dimensions:
            raise OpenAIResponseError(f"OpenAI embedding returned {len(embedding)} dimensions, expected {self.embedding_dimensions}.")
        return embedding

    def structured_json(self, prompt: str) -> dict[str, Any]:
        try:
            response = self._request_with_retry(
                "OpenAI generation request",
                lambda: self._client().chat.completions.create(
                    model=self.chat_model,
                    messages=[
                        {"role": "system", "content": "Return only valid JSON. Do not include markdown."},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                ),
            )
            content = response.choices[0].message.content if response.choices else ""
        except OpenAIServiceError:
            raise
        except Exception as exc:
            raise self._request_error("OpenAI generation request", exc) from exc
        if not content:
            raise OpenAIResponseError("OpenAI generation response was empty.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenAIResponseError("OpenAI generation response was not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise OpenAIResponseError("OpenAI generation response must be a JSON object.")
        return parsed

    def _request_with_retry(self, label: str, request: Any) -> Any:
        for attempt in range(3):
            try:
                return request()
            except OpenAIServiceError:
                raise
            except Exception as exc:
                if not is_retryable_rate_limit(exc) or attempt == 2:
                    raise self._request_error(label, exc) from exc
                time.sleep(retry_delay_seconds(exc, attempt))
        raise OpenAIResponseError(f"{label} failed.")

    def _request_error(self, label: str, exc: Exception) -> OpenAIResponseError:
        code = openai_error_code(exc)
        if is_quota_error(exc):
            return OpenAIResponseError(f"{label} failed because the OpenAI API quota or billing limit was reached. Check API billing and usage limits.")
        if is_rate_limit_error(exc):
            detail = f"{label} hit the OpenAI rate limit. Wait a moment and retry, or reduce request volume."
            if code:
                detail += f" OpenAI error code: {code}."
            return OpenAIRateLimitError(detail)
        return OpenAIResponseError(f"{label} failed: {type(exc).__name__}")


def is_rate_limit_error(exc: Exception) -> bool:
    return type(exc).__name__ == "RateLimitError" or getattr(exc, "status_code", None) == 429


def is_retryable_rate_limit(exc: Exception) -> bool:
    return is_rate_limit_error(exc) and not is_quota_error(exc)


def is_quota_error(exc: Exception) -> bool:
    return openai_error_code(exc) in {"insufficient_quota", "billing_hard_limit_reached"}


def openai_error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        body_code = body.get("code")
        if body_code:
            return str(body_code)
        error = body.get("error")
        if isinstance(error, dict) and error.get("code"):
            return str(error["code"])
    return ""


def retry_delay_seconds(exc: Exception, attempt: int) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return min(float(retry_after), 5.0)
            except ValueError:
                pass
    return 0.75 * (2**attempt)


openai_client = OpenAIClient()
