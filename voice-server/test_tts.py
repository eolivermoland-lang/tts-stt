"""Rask test av stemmekloningen uten API-server."""

import os
from pathlib import Path

from mlx_audio.tts.generate import generate_audio
from mlx_audio.tts.utils import load_model

BASE_DIR = Path(__file__).resolve().parent
LOCAL_8BIT = BASE_DIR / "models" / "chatterbox-v3-8bit"
MODEL_ID = os.getenv(
    "MODEL_ID",
    str(LOCAL_8BIT)
    if LOCAL_8BIT.exists()
    else "mlx-community/chatterbox-multilingual-v3",
)
REF = Path(os.getenv("REF_AUDIO", str(BASE_DIR / "min_stemme.wav"))).resolve()
OUT = BASE_DIR / "test_output.wav"

if not REF.exists():
    raise SystemExit(f"Fant ikke {REF}. Spill inn stemmen din forst.")

print("Laster modell ...")
model = load_model(MODEL_ID)

print("Genererer ...")
generate_audio(
    text="Hei! Jeg er Bingo, og jeg snakker med din stemme.",
    model=model,
    ref_audio=str(REF),
    lang_code="no",
    file_prefix=str(OUT.with_suffix("")),
    join_audio=True,
    verbose=True,
)

print(f"Ferdig: {OUT}")
