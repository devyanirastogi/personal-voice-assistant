import sounddevice as sd
from audio_in import listen_utterances, RATE

for audio in listen_utterances():            # Loops forever, one utterance at a time.
    print(f"utterance: {len(audio) / RATE:.1f} seconds, peak {abs(audio).max():.3f}")
    sd.play(audio, RATE)                     # Play it back so you can HEAR what was captured.
    sd.wait()                                # Wait until playback finishes.