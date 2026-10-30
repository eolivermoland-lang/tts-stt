#!/usr/bin/env python3
"""Testklient for Bingo: snakk -> STT -> chat -> TTS -> hør svaret."""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_API = "https://robot-dog-api.eolivermoland.workers.dev"

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_MS = 30
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_MS / 1000)
MIN_RECORD_SECONDS = 0.25
TRIM_THRESHOLD = 0.008  # ca. -42 dBFS
HISTORY_MESSAGES = 12


class ApiError(RuntimeError):
    """Feil fra API-et eller nettverket."""


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def load_config(args: argparse.Namespace) -> tuple[str, str]:
    env = load_env(BASE_DIR / ".env")
    api = (
        args.api
        or os.environ.get("API_URL")
        or env.get("API_URL")
        or DEFAULT_API
    ).rstrip("/")

    token = os.environ.get("ROBOT_TOKEN") or env.get("ROBOT_TOKEN") or ""
    if not token or token == "CHANGE_ME":
        for candidate in (
            BASE_DIR / ".robot_token",
            Path.home() / "robot-dog-api" / ".robot_token",
        ):
            if candidate.exists():
                token = candidate.read_text(encoding="utf-8").strip()
                break

    if not token or token == "CHANGE_ME":
        raise SystemExit(
            "ROBOT_TOKEN mangler. Kjør ./setup.sh, eller legg tokenet i .env."
        )

    return api, token


def api_request(
    api: str,
    token: str,
    path: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    timeout: float = 60.0,
) -> tuple[int, str, bytes]:
    url = f"{api}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "BingoVoiceChat/1.0",
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
                response.status,
                response.headers.get_content_type(),
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace").strip()
        detail = f"HTTP {exc.code}"
        if body:
            detail += f": {body[:500]}"
        raise ApiError(detail) from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"Får ikke kontakt med {url}: {exc.reason}") from exc


def check_status(api: str, token: str) -> None:
    _, _, body = api_request(api, token, "/status", timeout=15)
    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ApiError(f"Ugyldig svar fra /status: {body[:200]!r}") from exc
    if not data.get("ok"):
        raise ApiError(f"/status svarte: {data}")


def speech_to_text(api: str, token: str, wav_data: bytes) -> str:
    _, _, body = api_request(
        api,
        token,
        "/stt",
        data=wav_data,
        content_type="audio/wav",
        timeout=90,
    )
    try:
        return str(json.loads(body).get("text", "")).strip()
    except json.JSONDecodeError as exc:
        raise ApiError(f"Ugyldig svar fra /stt: {body[:200]!r}") from exc


def ask_llm(api: str, token: str, messages: list[dict[str, str]]) -> str:
    payload = json.dumps({"messages": messages}).encode("utf-8")
    _, _, body = api_request(
        api,
        token,
        "/chat",
        data=payload,
        content_type="application/json",
        timeout=60,
    )
    try:
        return str(json.loads(body).get("text", "")).strip()
    except json.JSONDecodeError as exc:
        raise ApiError(f"Ugyldig svar fra /chat: {body[:200]!r}") from exc


def text_to_speech(api: str, token: str, text: str) -> bytes:
    payload = json.dumps({"text": text}).encode("utf-8")
    _, content_type, body = api_request(
        api,
        token,
        "/say",
        data=payload,
        content_type="application/json",
        timeout=120,
    )
    if not body.startswith(b"RIFF"):
        raise ApiError(
            f"/say returnerte ikke WAV (content-type={content_type}, {len(body)} bytes)"
        )
    return body


def record_push_to_talk(device: int | None) -> np.ndarray:
    frames: list[np.ndarray] = []
    audio_errors: list[str] = []

    def callback(indata, frames_count, time_info, status):
        if status:
            audio_errors.append(str(status))
        frames.append(indata.copy())

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        blocksize=BLOCK_SIZE,
        device=device,
        callback=callback,
    ):
        print("Snakk nå! Trykk Enter når du er ferdig.", flush=True)
        print("\a", end="", flush=True)
        input()

    if audio_errors:
        print(f"Merknad fra lydkortet: {audio_errors[-1]}")

    if not frames:
        return np.zeros((0, 1), dtype=np.int16)

    return np.concatenate(frames, axis=0)


def trim_silence(audio: np.ndarray) -> np.ndarray:
    if audio.size == 0:
        return audio

    x = audio.astype(np.float32).reshape(-1) / 32768.0
    frame_size = max(1, int(SAMPLE_RATE * 0.02))
    frame_count = len(x) // frame_size
    if frame_count == 0:
        return audio

    frames = x[: frame_count * frame_size].reshape(frame_count, frame_size)
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    noise = float(np.percentile(rms, 10))
    threshold = max(TRIM_THRESHOLD, noise * 3.0)
    active = np.where(rms > threshold)[0]

    if active.size == 0:
        return np.zeros((0, 1), dtype=np.int16)

    start_frame = max(0, int(active[0]) - int(0.20 / 0.02))
    end_frame = min(frame_count, int(active[-1]) + int(0.30 / 0.02) + 1)
    return audio[start_frame * frame_size : end_frame * frame_size]


def wav_bytes(audio: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.astype(np.int16, copy=False).tobytes())
    return buffer.getvalue()


def play_wav(data: bytes) -> None:
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frames = wav.readframes(wav.getnframes())

        if sample_width != 2:
            raise ValueError(f"uventet samplebredde: {sample_width}")

        audio = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            audio = (
                audio.reshape(-1, channels).astype(np.float32).mean(axis=1)
            ).astype(np.int16)

        sd.play(audio, sample_rate)
        sd.wait()
        return
    except Exception as exc:
        print(f"(Bruker afplay i stedet: {exc})")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        subprocess.run(["afplay", tmp_path], check=True)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def list_devices() -> None:
    print(sd.query_devices())
    print("\nBruk f.eks. --device 1 for å velge inndataenhet.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Snakk med Bingo via STT, chat og TTS."
    )
    parser.add_argument(
        "--api",
        help="API-base-URL (standard: ROBOT_DOG_API eller .env)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="inndataenhet (se --list-devices)",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="vis lydenheter og avslutt",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_devices:
        list_devices()
        return 0

    api, token = load_config(args)

    print("=" * 62)
    print("  Bingo voice chat")
    print("=" * 62)
    print(f"API: {api}")
    print("Sjekker API ...", end=" ", flush=True)
    try:
        check_status(api, token)
    except ApiError as exc:
        print("FEIL")
        print(f"\n{exc}")
        print("\nSjekk at Workeren er deployet, og at ROBOT_TOKEN er riktig.")
        return 1
    print("OK")

    try:
        input_name = sd.query_devices(kind="input")["name"]
    except Exception:
        input_name = "ukjent"

    print(
        f"\nMikrofon: {input_name}\n"
        "Trykk Enter for å snakke. Trykk Enter igjen for å stoppe opptaket.\n"
        "Kommandoer: [t] skriv tekst, [r] nullstill samtalen, [q] avslutt."
    )

    history: list[dict[str, str]] = []

    try:
        while True:
            try:
                command = input("\n[Enter] snakk  [t] tekst  [r] reset  [q] avslutt > ")
            except EOFError:
                print()
                break

            command = command.strip()
            lowered = command.lower()

            if lowered in {"q", "quit", "exit"}:
                break
            if lowered in {"r", "reset"}:
                history.clear()
                print("Samtalen er nullstilt.")
                continue

            stt_seconds: float | None = None
            text = ""

            if lowered in {"t", "tekst"}:
                text = input("Skriv meldingen din: ").strip()
                if not text:
                    continue
            elif command == "":
                try:
                    audio = record_push_to_talk(args.device)
                except sd.PortAudioError as exc:
                    print(f"Lydfeil: {exc}")
                    print("Prøv --list-devices og velg en annen --device.")
                    continue

                audio = trim_silence(audio)
                duration = len(audio) / SAMPLE_RATE
                if duration < MIN_RECORD_SECONDS:
                    print("Jeg hørte ingenting. Prøv igjen.")
                    continue

                print(f"Sender {duration:.1f}s lyd til STT ...", flush=True)
                started = time.perf_counter()
                text = speech_to_text(api, token, wav_bytes(audio))
                stt_seconds = time.perf_counter() - started
                if not text:
                    print("STT fant ingen tekst. Prøv igjen.")
                    continue
            else:
                # Det går også an å bare skrive en melding direkte.
                text = command

            print(f"Du: {text}")

            messages = history + [{"role": "user", "content": text}]
            print("Bingo tenker ...", flush=True)
            started = time.perf_counter()
            reply = ask_llm(api, token, messages)
            chat_seconds = time.perf_counter() - started

            if not reply:
                print("Bingo svarte tomt. Prøv igjen.")
                continue

            print(f"Bingo: {reply}")

            print("Lager tale ...", flush=True)
            started = time.perf_counter()
            audio_reply = text_to_speech(api, token, reply)
            tts_seconds = time.perf_counter() - started

            print("Spiller av ...", flush=True)
            play_wav(audio_reply)

            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": reply})
            history = history[-HISTORY_MESSAGES:]

            parts = []
            if stt_seconds is not None:
                parts.append(f"STT {stt_seconds:.2f}s")
            parts.append(f"chat {chat_seconds:.2f}s")
            parts.append(f"TTS {tts_seconds:.2f}s")
            print("Tid: " + " | ".join(parts))

    except KeyboardInterrupt:
        print("\nAvslutter.")
    finally:
        sd.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
