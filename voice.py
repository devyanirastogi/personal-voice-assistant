import subprocess                            # Runs afplay for the listening tone.
import threading
import time
import tomllib
from pathlib import Path
import numpy as np
import agent
import memory
import speech
from audio_in import listen_utterances
from stt import transcribe
from wake import extract_command

config = tomllib.loads(Path("config.toml").read_text())
FOLLOW_UP = config["wake"]["follow_up_seconds"]
WAKE_REPLY = config["wake"]["wake_reply"]
ECHO_TAIL = config["audio"]["echo_tail_seconds"]

# Shared state: the listener thread WRITES it, the web page only READS it.
state = {"status": "loading", "muted": False, "turns": [], "error": "", "mute_until": 0.0}
turn_lock = threading.Lock()                 # Only one command may be processed at a time.
awake_until = 0.0                            # Follow-up window end time.
needs_flush = False                          # True after Loop speaks: discard stale mic audio.


def consume_flush():
    """Tell the mic code whether to discard buffered audio, and reset the flag."""
    global needs_flush
    result, needs_flush = needs_flush, False
    return result


def is_muted():
    """True when the mic should be ignored: manual mute, Loop speaking, or the echo tail."""
    return state["muted"] or speech.is_speaking() or time.time() < state["mute_until"]


def current_status():
    """The one word the web banner shows: loading, listening, thinking, speaking, muted or error."""
    if state["status"] in ("loading", "error"):
        return state["status"]
    if state["muted"]:
        return "muted"
    if speech.is_speaking():
        return "speaking"
    return state["status"]                   # "listening" or "thinking"


def beep():
    """A short tone that means: listening again."""
    subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])   # macOS built-in sound.


def run_turn(command, heard, source):
    """Run one command through the agent, speak the reply, and record the turn for the page."""
    global awake_until, needs_flush
    with turn_lock:                          # Wait if another command is still running.
        turn = {"time": time.strftime("%H:%M:%S"), "source": source,
                "heard": heard, "tools": [], "reply": ""}
        state["turns"].append(turn)
        state["turns"] = state["turns"][-20:]            # Keep only the last 20 turns.
        state["status"] = "thinking"
        try:
            turn["reply"] = agent.ask(command, on_sentence=speech.speak, trace=turn["tools"])
        except Exception as error:           # A crash in one turn must not kill the listener.
            turn["reply"] = f"Error: {error}"
        print(f"   [reply] {turn['reply']}")
        speech.wait_until_done()             # Let the voice finish.
        needs_flush = True
        awake_until = time.time() + FOLLOW_UP
        state["mute_until"] = time.time() + ECHO_TAIL    # Keep the mic muted a moment for the echo.
        memory.extract_in_background(command)            # Save personal facts without slowing the reply.
        state["status"] = "listening"


def submit_typed(text):
    """Called by the web page: run a typed command in its own thread so the page doesn't freeze."""
    threading.Thread(target=run_turn, args=(text, text, "typed"), daemon=True).start()


def handle(text):
    """Decide what to do with one transcribed utterance from the microphone."""
    global awake_until, needs_flush
    woke, command = extract_command(text)
    in_window = time.time() < awake_until
    if not woke and not in_window:
        print(f"   [ignored] {text}   (window left: {max(0.0, awake_until - time.time()):.1f}s)")
        return
    if not woke:
        command = text                       # Follow-up: the whole text is the command.
    if not command:                          # Only "Okay, Loop.": ask for the command.
        speech.speak(WAKE_REPLY)
        speech.wait_until_done()
        needs_flush = True
        awake_until = time.time() + FOLLOW_UP
        return
    print(f"   [command] {command}")
    run_turn(command, text, "voice")


def listener_loop():
    """The always-on loop. Started once, in a background thread."""
    try:
        state["status"] = "loading"
        transcribe(np.zeros(16000, dtype="float32"))     # Warm up Whisper.
        agent.warm_up()                                  # Warm up the chat model.
        state["status"] = "listening"
        print("Ready. Say: 'Loop, ...'")
        for audio in listen_utterances(is_muted=is_muted, should_flush=consume_flush):
            state["status"] = "thinking"                 # Transcribing and thinking.
            text = transcribe(audio)
            print(f'heard: "{text}"')
            if text:
                handle(text)
            if needs_flush:
                beep()                                   # Tell the user we're listening again.
            time.sleep(ECHO_TAIL)
            state["status"] = "listening"
    except Exception as error:               # Show any crash on the web page.
        state["status"] = "error"
        state["error"] = str(error)
        raise


if __name__ == "__main__":                   # Still works without the web page: python voice.py
    listener_loop()