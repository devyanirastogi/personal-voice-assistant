import time
from audio_in import listen_utterances
from stt import transcribe

print("Loading Whisper (first run downloads the model)...")
transcribe(__import__("numpy").zeros(16000, dtype="float32"))   # Warm-up: load the model before we need it.
print("Ready. Speak.")

for audio in listen_utterances():
    started = time.perf_counter()
    text = transcribe(audio)                 # Audio in, text out.
    print(f'heard: "{text}"   ({time.perf_counter() - started:.1f}s)')