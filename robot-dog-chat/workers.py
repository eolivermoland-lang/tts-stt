from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from api_client import ApiClient


class TurnWorker(QThread):
    transcribed = Signal(str, float)
    replied = Signal(str, float)
    audio_ready = Signal(bytes, float)
    failed = Signal(str)

    def __init__(
        self,
        client: ApiClient,
        *,
        text: str | None = None,
        wav_data: bytes | None = None,
        history: list[dict[str, str]],
        system: str,
        model: str,
        temperature: float,
        max_tokens: int,
        voice: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.text = text
        self.wav_data = wav_data
        self.history = history
        self.system = system
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.voice = voice

    def run(self) -> None:
        try:
            spoken_text = (self.text or "").strip()

            if self.wav_data is not None:
                started = time.perf_counter()
                spoken_text = self.client.speech_to_text(self.wav_data)
                self.transcribed.emit(
                    spoken_text, time.perf_counter() - started
                )
                if not spoken_text:
                    raise RuntimeError("STT fant ingen tekst")

            if not spoken_text:
                raise RuntimeError("Tom melding")

            messages = self.history + [
                {"role": "user", "content": spoken_text}
            ]
            started = time.perf_counter()
            reply = self.client.chat(
                messages,
                system=self.system,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            self.replied.emit(reply, time.perf_counter() - started)
            if not reply:
                raise RuntimeError("Modellen svarte tomt")

            started = time.perf_counter()
            audio = self.client.say(reply, self.voice)
            self.audio_ready.emit(audio, time.perf_counter() - started)
        except Exception as exc:
            self.failed.emit(str(exc))


class ApiInfoWorker(QThread):
    result = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: ApiClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self) -> None:
        result: dict = {"status": None, "voices": None, "errors": []}
        try:
            result["status"] = self.client.status()
        except Exception as exc:
            result["errors"].append(f"Status: {exc}")

        try:
            result["voices"] = self.client.voices()
        except Exception as exc:
            result["errors"].append(f"Stemmer/TTS: {exc}")

        self.result.emit(result)


class ReloadVoicesWorker(QThread):
    result = Signal(dict)
    failed = Signal(str)

    def __init__(self, client: ApiClient, parent=None):
        super().__init__(parent)
        self.client = client

    def run(self) -> None:
        try:
            reload_result = self.client.reload_voices()
            voice_result = self.client.voices()
            self.result.emit(
                {"reload": reload_result, "voices": voice_result}
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class PreviewWorker(QThread):
    audio_ready = Signal(bytes)
    failed = Signal(str)

    def __init__(
        self,
        client: ApiClient,
        text: str,
        voice: dict,
        parent=None,
    ):
        super().__init__(parent)
        self.client = client
        self.text = text
        self.voice = voice

    def run(self) -> None:
        try:
            self.audio_ready.emit(self.client.say(self.text, self.voice))
        except Exception as exc:
            self.failed.emit(str(exc))
