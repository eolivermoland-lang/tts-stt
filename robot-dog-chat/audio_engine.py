from __future__ import annotations

import io
import os
import subprocess
import tempfile
import threading
import time
import wave
from collections import deque

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QThread, Signal

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
BLOCK_MS = 30
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_MS / 1000)
TRIM_FLOOR = 0.008


def list_input_devices() -> list[dict]:
    devices = []
    try:
        for index, device in enumerate(sd.query_devices()):
            channels = int(device.get("max_input_channels", 0))
            if channels > 0:
                devices.append(
                    {
                        "index": index,
                        "name": device.get("name", f"Enhet {index}"),
                        "channels": channels,
                        "sample_rate": int(
                            device.get("default_samplerate", SAMPLE_RATE)
                        ),
                    }
                )
    except Exception:
        pass
    return devices


def list_output_devices() -> list[dict]:
    devices = []
    try:
        for index, device in enumerate(sd.query_devices()):
            channels = int(device.get("max_output_channels", 0))
            if channels > 0:
                devices.append(
                    {
                        "index": index,
                        "name": device.get("name", f"Enhet {index}"),
                        "channels": channels,
                        "sample_rate": int(
                            device.get("default_samplerate", SAMPLE_RATE)
                        ),
                    }
                )
    except Exception:
        pass
    return devices


def default_input_index() -> int | None:
    try:
        selected = sd.default.device
        try:
            index = selected[0]
        except (TypeError, IndexError):
            index = selected
        if index is not None and int(index) >= 0:
            return int(index)
    except Exception:
        pass
    return None


def default_output_index() -> int | None:
    try:
        selected = sd.default.device
        try:
            index = selected[1]
        except (TypeError, IndexError):
            index = selected
        if index is not None and int(index) >= 0:
            return int(index)
    except Exception:
        pass
    return None


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
    threshold = max(TRIM_FLOOR, noise * 3.0)
    active = np.where(rms > threshold)[0]

    if active.size == 0:
        return np.zeros((0, CHANNELS), dtype=np.int16)

    start = max(0, int(active[0]) - int(0.18 / 0.02))
    end = min(frame_count, int(active[-1]) + int(0.28 / 0.02) + 1)
    return audio[start * frame_size : end * frame_size]


def wav_bytes(audio: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(CHANNELS)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(
            audio.astype(np.int16, copy=False).reshape(-1).tobytes()
        )
    return buffer.getvalue()


def read_wav(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise ValueError(f"uventet samplebredde: {sample_width}")

    audio = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        audio = (
            audio.reshape(-1, channels).astype(np.float32).mean(axis=1)
        ).astype(np.int16)
    return audio, sample_rate


class RecorderSignals(QObject):
    level = Signal(float)
    finished = Signal(object, str)
    error = Signal(str)


class Recorder:
    def __init__(self):
        self.signals = RecorderSignals()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(
        self,
        *,
        mode: str,
        device: int | None,
        threshold_db: float,
        silence_ms: int,
        max_seconds: float,
        pre_roll_ms: int,
        trim: bool,
    ) -> None:
        if self.is_running:
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            kwargs={
                "mode": mode,
                "device": device,
                "threshold_db": threshold_db,
                "silence_ms": silence_ms,
                "max_seconds": max_seconds,
                "pre_roll_ms": pre_roll_ms,
                "trim": trim,
            },
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(
        self,
        *,
        mode: str,
        device: int | None,
        threshold_db: float,
        silence_ms: int,
        max_seconds: float,
        pre_roll_ms: int,
        trim: bool,
    ) -> None:
        audio_blocks: list[np.ndarray] = []
        pre_roll_blocks = max(1, int(pre_roll_ms / BLOCK_MS))
        pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_blocks)
        speech_started = False
        silence_since: float | None = None
        started = time.monotonic()
        reason = "stopped"

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                blocksize=BLOCK_SIZE,
                device=device,
                latency="low",
            ) as stream:
                while not self._stop.is_set():
                    data, overflowed = stream.read(BLOCK_SIZE)
                    block = np.asarray(data).copy()
                    if overflowed:
                        pass

                    samples = block.astype(np.float32).reshape(-1)
                    rms = float(np.sqrt(np.mean(samples * samples))) / 32768.0
                    level_db = 20.0 * np.log10(max(rms, 1e-9))
                    self.signals.level.emit(float(level_db))

                    now = time.monotonic()
                    elapsed = now - started

                    if mode == "ptt":
                        audio_blocks.append(block)
                        if elapsed >= max_seconds:
                            reason = "max"
                            break
                        continue

                    if not speech_started:
                        pre_roll.append(block)
                        if level_db >= threshold_db:
                            speech_started = True
                            audio_blocks.extend(pre_roll)
                            pre_roll.clear()
                            silence_since = None
                        elif elapsed >= 8.0:
                            reason = "timeout"
                            break
                        continue

                    audio_blocks.append(block)
                    if level_db < threshold_db:
                        if silence_since is None:
                            silence_since = now
                        elif now - silence_since >= silence_ms / 1000.0:
                            reason = "vad"
                            break
                    else:
                        silence_since = None

                    if elapsed >= max_seconds:
                        reason = "max"
                        break

            if audio_blocks:
                audio = np.concatenate(audio_blocks, axis=0)
                if trim:
                    audio = trim_silence(audio)
            else:
                audio = np.zeros((0, CHANNELS), dtype=np.int16)

            self.signals.finished.emit(audio, reason)
        except Exception as exc:
            self.signals.error.emit(str(exc))


class PlaybackThread(QThread):
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, data: bytes, device: int | None = None, parent=None):
        super().__init__(parent)
        self.data = data
        self.device = device

    def run(self) -> None:
        temp_path: str | None = None
        try:
            audio, sample_rate = read_wav(self.data)
            try:
                sd.play(audio, sample_rate, device=self.device)
                sd.wait()
            except Exception:
                # Hvis valgt utgang ikke virker, prov systemutgangen.
                try:
                    sd.stop()
                    sd.play(audio, sample_rate, device=None)
                    sd.wait()
                except Exception:
                    with tempfile.NamedTemporaryFile(
                        suffix=".wav", delete=False
                    ) as tmp:
                        tmp.write(self.data)
                        temp_path = tmp.name
                    subprocess.run(["afplay", temp_path], check=True)
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def stop(self) -> None:
        sd.stop()
