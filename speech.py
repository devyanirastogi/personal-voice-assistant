import queue                                 # A thread-safe waiting line for sentences.
import re                                    # Pattern matching for cleaning text.
import subprocess                            # Lets Python run other programs, like macOS `say`.
import threading                             # Lets one piece of code run in the background.
import tomllib
from pathlib import Path

config = tomllib.loads(Path("config.toml").read_text())
VOICE = config["speech"]["voice"]            # Which macOS voice to use.
RATE = config["speech"]["rate"]              # Words per minute.

_queue = queue.Queue()                       # Sentences waiting to be spoken.
_lock = threading.Lock()                     # Stops two threads changing shared values at once.
_current = None                              # The `say` process that is speaking right now.
_generation = 0                              # Goes up on every stop(); old sentences are then skipped.


def clean(text):
    """Remove characters a voice would read badly, like asterisks and backticks."""
    text = re.sub(r"[*#`_~>]", "", text)     # Delete markdown symbols.
    return re.sub(r"\s+", " ", text).strip() # Collapse extra spaces and newlines.


def _worker():
    """Background loop: take one sentence at a time and speak it."""
    global _current
    while True:
        generation, sentence = _queue.get()  # Wait here until a sentence arrives.
        proc = None
        with _lock:
            if generation == _generation:    # Skip sentences queued before the last stop().
                proc = _current = subprocess.Popen(      # Start `say` without waiting for it to finish.
                    ["say", "-v", VOICE, "-r", str(RATE), sentence])
        if proc:
            proc.wait()                      # Wait until this sentence is done speaking.
            with _lock:
                _current = None
        _queue.task_done()                   # Tell the queue this sentence is finished.


threading.Thread(target=_worker, daemon=True).start()   # Start the background speaker once, on import.


def speak(text):
    """Queue text to be spoken. Returns immediately."""
    text = clean(text)
    if text:
        _queue.put((_generation, text))      # Remember which "generation" this sentence belongs to.


def stop():
    """Silence the voice at once and drop everything still waiting."""
    global _generation
    with _lock:
        _generation += 1                     # All queued sentences are now out of date and will be skipped.
        if _current and _current.poll() is None:   # poll() is None while the process is still running.
            _current.terminate()             # Kill the `say` process: sound stops immediately.


def is_speaking():
    """True while anything is speaking or waiting to be spoken."""
    return _queue.unfinished_tasks > 0       # Stage 3 uses this to mute the microphone.


def wait_until_done():
    """Block until all queued speech has finished."""
    _queue.join()