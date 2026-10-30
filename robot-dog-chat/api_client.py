from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "BingoStudio/1.0"


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class ApiClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()

    def _request(
        self,
        path: str,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
        timeout: float = 60.0,
    ) -> tuple[str, bytes]:
        url = f"{self.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json, audio/wav",
        }
        if content_type:
            headers["Content-Type"] = content_type

        req = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method="POST" if data is not None else "GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return (
                    response.headers.get_content_type(),
                    response.read(),
                )
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", "replace").strip()
            detail = raw
            try:
                parsed = json.loads(raw)
                detail = (
                    parsed.get("detail")
                    or parsed.get("error")
                    or parsed.get("message")
                    or raw
                )
                if not isinstance(detail, str):
                    detail = json.dumps(detail, ensure_ascii=False)
            except json.JSONDecodeError:
                pass

            message = f"HTTP {exc.code}"
            if detail:
                message += f": {detail[:500]}"
            raise ApiError(message, exc.code) from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"Får ikke kontakt med {url}: {exc.reason}") from exc

    @staticmethod
    def _json(content_type: str, body: bytes) -> dict[str, Any]:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            preview = body[:200].decode("utf-8", "replace")
            raise ApiError(
                f"Ugyldig JSON-svar ({content_type}): {preview!r}"
            ) from exc
        if not isinstance(data, dict):
            raise ApiError("API-et returnerte ikke et JSON-objekt")
        return data

    def status(self) -> dict[str, Any]:
        content_type, body = self._request("/status", timeout=15)
        return self._json(content_type, body)

    def voices(self) -> dict[str, Any]:
        content_type, body = self._request("/voices", timeout=30)
        return self._json(content_type, body)

    def reload_voices(self) -> dict[str, Any]:
        content_type, body = self._request(
            "/voices/reload",
            data=b"",
            content_type="application/json",
            timeout=180,
        )
        return self._json(content_type, body)

    def speech_to_text(self, wav_data: bytes) -> str:
        content_type, body = self._request(
            "/stt",
            data=wav_data,
            content_type="audio/wav",
            timeout=90,
        )
        data = self._json(content_type, body)
        return str(data.get("text", "")).strip()

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = json.dumps(
            {
                "messages": messages,
                "system": system,
                "model": model,
                "temperature": temperature,
                "max_completion_tokens": max_tokens,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        content_type, body = self._request(
            "/chat",
            data=payload,
            content_type="application/json",
            timeout=60,
        )
        data = self._json(content_type, body)
        return str(data.get("text", "")).strip()

    def say(self, text: str, voice: dict[str, Any]) -> bytes:
        payload = json.dumps(
            {"text": text, **voice},
            ensure_ascii=False,
        ).encode("utf-8")
        content_type, body = self._request(
            "/say",
            data=payload,
            content_type="application/json",
            timeout=120,
        )
        if not body.startswith(b"RIFF"):
            preview = body[:200].decode("utf-8", "replace")
            raise ApiError(
                f"/say returnerte ikke WAV ({content_type}): {preview!r}"
            )
        return body
