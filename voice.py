import time
import tomllib
from pathlib import Path
import numpy as np
import agent                                 # The agent loop.
import speech                                # The voice.
from audio_in import listen_utterances       # Microphone to utterances.
from stt import transcribe                   # Utterance to text.
from wake import extract_command             # Wake word logic.

config = tomllib.loads(Path("config.toml").read_text())
FOLLOW_UP = config["wake"]["follow_up_seconds"]      # 8 seconds without needing the wake word.
WAKE_REPLY = config["wake"]["wake_reply"]            # What Loop says if you only say its name.
ECHO_TAIL = config["audio"]["echo_tail_seconds"]     # Silence after speaking, to let the echo die.

awake_until = 0.0                            # Clock time until which no wake word is needed.
needs_flush = False                          # Set to True whenever Loop speaks.


def consume_flush():
    """Tell the microphone code whether to discard buffered audio, and reset the flag."""
    global needs_flush
    result, needs_flush = needs_flush, False
    return result

def speak_and_wait(text):
    """Speak a short phrase and wait until it has finished."""
    global needs_flush
    speech.speak(text)
    speech.wait_until_done()
    needs_flush = True                          # The microphone should discard any audio that arrived while Loop was talking.


def handle(text):
    """Decide what to do with one transcribed utterance."""
    global awake_until, needs_flush
    woke, command = extract_command(text)    # Was the wake word said? What is the rest?
    in_window = time.time() < awake_until    # Are we still in the 8-second follow-up window?

    if not woke and not in_window:           # No wake word and not expecting one: ignore.
        print(f"   [ignored] {text}")
        return
    if not woke:                             # Follow-up: the whole text is the command.
        command = text
    if not command:                          # Only "Okay, Loop." was said: ask for the command.
        speak_and_wait(WAKE_REPLY)
        awake_until = time.time() + FOLLOW_UP
        return

    print(f"   [command] {command}")
    agent.ask(command, on_sentence=speech.speak)     # Run the agent; sentences are spoken as they arrive.
    speech.wait_until_done()                 # Wait for the voice to finish before listening again.
    needs_flush = True                          # The microphone should discard any audio that arrived while Loop was talking.
    awake_until = time.time() + FOLLOW_UP    # The window starts when the reply ENDS.


def main():
    print("Loading models...")
    transcribe(np.zeros(16000, dtype="float32"))     # Warm up Whisper.
    agent.warm_up()                          # Warm up the chat model.
    print("Ready. Say: 'Loop, ...'")
    for audio in listen_utterances(should_flush=consume_flush):        # One utterance at a time, forever.
        text = transcribe(audio)
        print(f'heard: "{text}"')
        if text:
            handle(text)
        time.sleep(ECHO_TAIL)                # Let the room go quiet before the next read.


if __name__ == "__main__":
    main()