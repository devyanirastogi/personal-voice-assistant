import sounddevice as sd                     # Reads audio from the microphone.
import numpy as np                           # Fast math on lists of numbers.

SAMPLE_RATE = 16000                          # 16,000 measurements per second (what Whisper expects).
BLOCK = 1600                                 # Read 1,600 samples at a time = 0.1 seconds.

with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                    blocksize=BLOCK) as stream:       # Open the mic: 1 channel, decimal numbers.
    print("Speak now (5 seconds)...")
    for _ in range(50):                      # 50 blocks x 0.1 s = 5 seconds.
        block, overflowed = stream.read(BLOCK)        # Wait for the next 0.1 s of audio.
        volume = float(np.sqrt(np.mean(block ** 2)))  # RMS: square, average, square root.
        print(f"{volume:.4f} " + "#" * int(volume * 300))   # Print the number plus a bar to see it.