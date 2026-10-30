"""
Lokal TTS-server for robothunden.

Kjorer Chatterbox Multilingual V3 via MLX paa Apple Silicon.
Kloner stemmen fra referanse-WAV-filer i voices/ (og min_stemme.wav).

Start:
    ./start.sh

Test:
    curl -X POST http://localhost:8000/say \
      -H "x-api-key: $(cat .secret)" \
      -H "content-type: application/json" \
      -d '{"text":"Hei, jeg er Bingo!","voice":"min_stemme"}' \
      --output svar.wav
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from mlx_audio.tts.generate import generate_audio
from mlx_audio.tts.utils import load_model
from mlx_audio.utils import load_audio

BASE_DIR = Path(__file__).resolve().parent
LOCAL_8BIT = BASE_DIR / "models" / "chatterbox-v3-8bit"
MODEL_ID = os.getenv(
    "MODEL_ID",
    str(LOCAL_8BIT)
    if LOCAL_8BIT.exists()
    else "mlx-community/chatterbox-multilingual-v3",
)
REF_AUDIO = Path(
    os.getenv("REF_AUDIO", str(BASE_DIR / "min_stemme.wav"))
).expanduser().resolve()
VOICES_DIR = Path(
    os.getenv("VOICES_DIR", str(BASE_DIR / "voices"))
).expanduser().resolve()
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "min_stemme")
TTS_SECRET = os.getenv("TTS_SECRET", "")
MAX_CHARS = int(os.getenv("MAX_CHARS", "400"))
CFG_WEIGHT = float(os.getenv("CFG_WEIGHT", "0.5"))
EXAGGERATION = float(os.getenv("EXAGGERATION", "0.5"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.8"))
REPETITION_PENALTY = float(os.getenv("REPETITION_PENALTY", "1.2"))
TOP_P = float(os.getenv("TOP_P", "1.0"))
LANG_CODE = os.getenv("TTS_LANG", "no")
VERBOSE = os.getenv("TTS_VERBOSE", "0") in {"1", "true", "True", "yes"}
CACHE_SIZE = int(os.getenv("CACHE_SIZE", "64"))

if not TTS_SECRET:
    raise SystemExit(
        "TTS_SECRET mangler. Kjor via ./start.sh, eller eksporter TTS_SECRET."
    )

app = FastAPI(title="Robot Dog TTS", version="2.0")
print(f"Laster modell: {MODEL_ID}")
model = load_model(MODEL_ID)

VOICE_FILES: dict[str, Path] = {}
CONDS: dict[str, object] = {}
TTS_LOCK = asyncio.Lock()


def voice_label(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").strip().title()


def wav_info(path: Path) -> dict[str, float | int | str]:
    try:
        with wave.open(str(path), "rb") as wav:
            return {
                "duration": round(wav.getnframes() / wav.getframerate(), 2),
                "sample_rate": wav.getframerate(),
                "channels": wav.getnchannels(),
            }
    except Exception:
        return {"duration": 0, "sample_rate": 0, "channels": 0}


def discover_voices() -> dict[str, Path]:
    found: dict[str, Path] = {}

    if REF_AUDIO.exists():
        found[REF_AUDIO.stem] = REF_AUDIO
        if DEFAULT_VOICE and DEFAULT_VOICE not in found:
            found[DEFAULT_VOICE] = REF_AUDIO

    if VOICES_DIR.exists():
        for path in sorted(VOICES_DIR.glob("*.wav")):
            if path.is_file() and path.stat().st_size > 1024:
                found[path.stem] = path.resolve()

    return found


def prepare_voice(name: str, path: Path) -> object:
    print(f"Forbereder stemme: {name} ({path})")
    ref_wav = load_audio(
        str(path),
        sample_rate=model.sample_rate,
        volume_normalize=False,
    )
    return model.prepare_conditionals(
        ref_wav,
        model.sample_rate,
        exaggeration=EXAGGERATION,
    )


def reload_voices() -> dict[str, object]:
    """Les stemmefiler paa nytt. Ma kjores paa MLX-traden."""
    global VOICE_FILES, CONDS

    new_files = discover_voices()
    new_conds: dict[str, object] = {}
    errors: dict[str, str] = {}

    for name, path in new_files.items():
        try:
            new_conds[name] = prepare_voice(name, path)
        except Exception as exc:
            errors[name] = str(exc)
            print(f"Kunne ikke laste stemme {name}: {exc}")

    VOICE_FILES = new_files
    CONDS = new_conds
    render.cache_clear()
    return {"voices": list(new_files), "errors": errors}


class SayBody(BaseModel):
    text: str
    voice: str | None = None
    exaggeration: float | None = None
    cfg_weight: float | None = None
    temperature: float | None = None
    repetition_penalty: float | None = None
    top_p: float | None = None
    lang_code: str | None = None
    max_tokens: int | None = None


def clamp(value: float | int | None, default: float | int, low, high):
    if value is None:
        return default
    return max(low, min(high, value))


@lru_cache(maxsize=CACHE_SIZE)
def render(
    text: str,
    voice: str,
    exaggeration: float,
    cfg_weight: float,
    temperature: float,
    repetition_penalty: float,
    top_p: float,
    lang_code: str,
    max_tokens: int,
) -> bytes:
    conds = CONDS.get(voice)
    path = VOICE_FILES.get(voice)

    with tempfile.TemporaryDirectory() as tmp:
        prefix = os.path.join(tmp, "out")

        gen_kwargs = {
            "text": text,
            "model": model,
            "lang_code": lang_code,
            "cfg_weight": cfg_weight,
            "temperature": temperature,
            "repetition_penalty": repetition_penalty,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "file_prefix": prefix,
            "join_audio": True,
            "verbose": VERBOSE,
        }
        if conds is not None:
            gen_kwargs["conds"] = conds
            gen_kwargs["exaggeration"] = exaggeration
        elif path is not None:
            gen_kwargs["ref_audio"] = str(path)
            gen_kwargs["exaggeration"] = exaggeration
        else:
            raise RuntimeError(f"stemmen finnes ikke: {voice}")

        generate_audio(**gen_kwargs)

        out_path = Path(prefix + ".wav")
        if not out_path.exists():
            raise RuntimeError("TTS produserte ingen lyd")

        return out_path.read_bytes()


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "model": MODEL_ID,
            "default_voice": DEFAULT_VOICE,
            "voices": list(VOICE_FILES),
            "voice_dir": str(VOICES_DIR),
            "cache": render.cache_info()._asdict(),
        }
    )


@app.get("/voices")
def list_voices(x_api_key: str = Header(default="")) -> JSONResponse:
    if x_api_key != TTS_SECRET:
        raise HTTPException(status_code=401, detail="feil API-nokkel")

    voices = []
    for name, path in VOICE_FILES.items():
        info = wav_info(path)
        voices.append(
            {
                "name": name,
                "label": voice_label(name),
                "default": name == DEFAULT_VOICE or path == REF_AUDIO,
                **info,
            }
        )

    return JSONResponse(
        {
            "ok": True,
            "default_voice": DEFAULT_VOICE,
            "voice_dir": str(VOICES_DIR),
            "voices": voices,
            "defaults": {
                "exaggeration": EXAGGERATION,
                "cfg_weight": CFG_WEIGHT,
                "temperature": TEMPERATURE,
                "repetition_penalty": REPETITION_PENALTY,
                "top_p": TOP_P,
                "lang_code": LANG_CODE,
                "max_tokens": 1000,
            },
        }
    )


@app.post("/voices/reload")
async def reload_voices_endpoint(
    x_api_key: str = Header(default=""),
) -> JSONResponse:
    if x_api_key != TTS_SECRET:
        raise HTTPException(status_code=401, detail="feil API-nokkel")

    async with TTS_LOCK:
        result = reload_voices()

    return JSONResponse({"ok": True, **result})


@app.post("/say")
async def say(body: SayBody, x_api_key: str = Header(default="")):
    if x_api_key != TTS_SECRET:
        raise HTTPException(status_code=401, detail="feil API-nokkel")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="tom tekst")
    if len(text) > MAX_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"teksten er for lang ({len(text)} > {MAX_CHARS} tegn)",
        )

    voice = (body.voice or DEFAULT_VOICE).strip()
    if voice not in VOICE_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"ukjent stemme: {voice}. Velg en av: {', '.join(VOICE_FILES)}",
        )
    if voice not in CONDS:
        raise HTTPException(
            status_code=500,
            detail=f"stemmen er ikke lastet: {voice}",
        )

    lang_code = (body.lang_code or LANG_CODE).strip().lower()
    if not re.fullmatch(r"[a-z]{2,3}", lang_code):
        raise HTTPException(status_code=400, detail="ugyldig språkkode")

    exaggeration = clamp(body.exaggeration, EXAGGERATION, 0.0, 1.0)
    cfg_weight = clamp(body.cfg_weight, CFG_WEIGHT, 0.0, 1.0)
    temperature = clamp(body.temperature, TEMPERATURE, 0.1, 2.0)
    repetition_penalty = clamp(
        body.repetition_penalty, REPETITION_PENALTY, 1.0, 2.0
    )
    top_p = clamp(body.top_p, TOP_P, 0.1, 1.0)
    max_tokens = int(clamp(body.max_tokens, 1000, 100, 2000))

    try:
        async with TTS_LOCK:
            data = render(
                text,
                voice,
                float(exaggeration),
                float(cfg_weight),
                float(temperature),
                float(repetition_penalty),
                float(top_p),
                lang_code,
                max_tokens,
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type="audio/wav",
        headers={"cache-control": "no-store"},
    )


if REF_AUDIO.exists() or VOICES_DIR.exists():
    print(f"Stemmemappe: {VOICES_DIR}")
    reload_voices()
    print(f"Stemmer klare: {', '.join(VOICE_FILES) or 'ingen'}")
else:
    print(f"Advarsel: referanselyd mangler: {REF_AUDIO}")

print("Modell lastet.")
