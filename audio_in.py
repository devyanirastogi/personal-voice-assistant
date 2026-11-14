import collections                           # Gives us deque, a list with a maximum length.
import tomllib
from pathlib import Path
import numpy as np
import sounddevice as sd

cfg = tomllib.loads(Path("config.toml").read_text())["audio"]   # The [audio] section of the config.
RATE = cfg["sample_rate"]                                        # 16000 samples per second.
BLOCK = int(RATE * cfg["block_ms"] / 1000)                       # Samples per block: 16000 * 0.05 = 800.
END_BLOCKS = round(cfg["silence_seconds"] * 1000 / cfg["block_ms"])      # Quiet blocks that end speech: 12.
PREROLL_BLOCKS = round(cfg["preroll_seconds"] * 1000 / cfg["block_ms"])  # Blocks kept from before speech: 6.
MAX_BLOCKS = round(cfg["max_seconds"] * 1000 / cfg["block_ms"])          # Longest allowed utterance.
MIN_LOUD_BLOCKS = 4                          # Fewer loud blocks than this is a click, not speech.


def volume_of(block):
    """RMS volume of a block of samples."""
    return float(np.sqrt(np.mean(block ** 2)))


def calibrate(stream, seconds=1.0):
    """Measure the room's noise for a second and return the speech threshold."""
    count = int(seconds * 1000 / cfg["block_ms"])
    levels = [volume_of(stream.read(BLOCK)[0]) for _ in range(count)]   # Volume of each block.
    noise = float(np.median(levels))         # Median ignores a stray cough or click.
    return max(noise * cfg["noise_multiplier"], cfg["min_threshold"])   # Never go below the minimum.


def listen_utterances(is_muted=lambda: False):
    """Open the mic and yield one numpy array of audio per spoken utterance, forever."""
    with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK) as stream:
        threshold = calibrate(stream)
        print(f"[audio] noise calibrated, speech threshold = {threshold:.4f}")
        preroll = collections.deque(maxlen=PREROLL_BLOCKS)   # Rolling buffer: old blocks fall off the end.
        utterance = []                       # Blocks of the speech being recorded.
        speaking = False
        loud_blocks = quiet_blocks = 0
        while True:
            block = stream.read(BLOCK)[0][:, 0]      # Next 50 ms. [:, 0] turns shape (800,1) into (800,).
            if is_muted():                   # Muted (e.g. Loop is talking): throw everything away.
                preroll.clear()
                utterance, speaking = [], False
                continue
            loud = volume_of(block) > threshold      # Is this block above the room noise?
            if not speaking:                 # State 1: waiting for speech.
                preroll.append(block)
                if loud:                     # Speech began: start with the pre-roll audio.
                    speaking = True
                    utterance = list(preroll)
                    loud_blocks, quiet_blocks = 1, 0
            else:                            # State 2: recording speech.
                utterance.append(block)
                if loud:
                    loud_blocks += 1
                    quiet_blocks = 0         # Any loud block resets the quiet counter.
                else:
                    quiet_blocks += 1
                if quiet_blocks >= END_BLOCKS or len(utterance) >= MAX_BLOCKS:   # Speech ended.
                    if loud_blocks >= MIN_LOUD_BLOCKS:
                        yield np.concatenate(utterance)  # Hand the full utterance to the caller.
                    speaking = False
                    utterance = []
                    preroll.clear()
