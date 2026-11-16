import tomllib
from pathlib import Path
import mlx_whisper                           # Whisper, optimized for Apple Silicon.
import numpy as np

cfg = tomllib.loads(Path("config.toml").read_text())["stt"]   # The [stt] section of the config.


def transcribe(audio):
    """Turn a numpy array of 16 kHz audio into text."""
    result = mlx_whisper.transcribe(
        audio.astype(np.float32),            # Whisper wants decimal numbers.
        path_or_hf_repo=cfg["model"],        # Which Whisper model to use (downloaded on first run).
        language=cfg.get("language", "en"),  # Skip language detection: it's faster and avoids guesses.
        initial_prompt=cfg.get("prompt"),    # A hint of words we expect, like the name "Loop".
        condition_on_previous_text=False,    # Treat each utterance separately.
    )
    return result["text"].strip()            # The recognized text, without extra spaces.