import json                                  # Turns tool results (dictionaries) into text for the model.
import tomllib                               # Reads config.toml.
from datetime import datetime                # Gives us the current date and time.
from pathlib import Path
import ollama                                # Talks to the local model.
import tools                                 # Your four appointment tools
import time
import re                                       # Regular expressions, for pattern matching in text.
import speech                                   # Speak text aloud and stop mid-sentence.
from datetime import datetime, timedelta     # timedelta lets us add days to a date.


config = tomllib.loads(Path("config.toml").read_text())   # Load settings.
CHAT = config["models"]["chat"]              # Which chat model to use.
THINK = config["models"].get("think", False) # Whether the model reasons silently first (default: no).
KEEP_ALIVE = config["models"].get("keep_alive", "5m")   # How long Ollama keeps the model loaded after a call.
CONTEXT = config["models"].get("context", 4096)         # How many tokens the model can see at once.
ACK = config["speech"].get("acknowledge", "")   # Short phrase spoken at once. Empty string turns it off.

# A lookup table: tool name -> the real Python function.
TOOLS = {f.__name__: f for f in [
    tools.create_appointment, tools.list_appointments,
    tools.update_appointment, tools.delete_appointment,
]}

history = []                                 # The conversation so far. Kept between turns so "move it" works.

def upcoming_days():
    """Return the next 8 days as text, e.g. 'Friday 2026-11-13 (today); Saturday 2026-11-14 (tomorrow); ...'."""
    today = datetime.now()
    parts = []
    for offset in range(8):                  # offset = 0 (today) through 7.
        day = today + timedelta(days=offset) # Add that many days to today.
        label = " (today)" if offset == 0 else " (tomorrow)" if offset == 1 else ""
        parts.append(f"{day.strftime('%A %Y-%m-%d')}{label}")   # e.g. "Friday 2026-11-13 (today)".
    return "; ".join(parts)                  # Join all 8 into one line.

def system_prompt():
    """Build the rules for the model. Rebuilt every request so the date is always current."""
    now = datetime.now().strftime("%A, %Y-%m-%d %H:%M")   # Current date and time.
    return f"""You are Loop, a voice assistant that manages the user's appointments.
The current date and time is {now}.
Calendar for the next days: {upcoming_days()}.
Rules:
- Convert day names to dates using the calendar above. A weekday name means the soonest such day after today. Never work out dates yourself.
- If the date, the time, or the location is missing or unclear (for example "at 3" with no AM or PM), ask one short question. Never guess or invent them.
- Never say something was booked, moved or deleted unless the tool just returned success. Read the id from the tool result.
- To delete: first find the appointment, ask the user to confirm with yes or no, and call delete only after they say yes.
- After a tool succeeds, do not call another tool to double-check. Just report the result.
- Answer only what was asked. Do not add extra questions or offers.
- Reply in one or two short sentences. No lists, no markdown, because your reply will be spoken aloud."""


def recent_user_text(last_n=3):
    """Return the user's last few messages joined into one lowercase string."""
    messages = [m["content"] for m in history
                if isinstance(m, dict) and m.get("role") == "user"]   # User messages are plain dicts; model replies are objects.
    return " ".join(messages[-last_n:]).lower()  # Take the last few, join them, lowercase them.


def grounding_error(name, args):
    """Return an error dict if a booking uses values the user never said, otherwise None."""
    if name != "create_appointment":             # Only check bookings.
        return None
    said = recent_user_text()                    # What the user actually said recently.
    location = str(args.get("location", "")).lower().strip()   # The location the model wants to use.
    if not location or location not in said:     # Not found anywhere in the user's words.
        return {"success": False,
                "error": "The user has not said where. Do not guess. Ask the user for the location."}
    time_pattern = (r"\b\d{1,2}(:\d{2})?\s*(am|pm|a\.m\.|p\.m\.)"   # "3pm", "3 pm", "3:30 pm"
                    r"|\b\d{1,2}:\d{2}\b"                           # "15:00"
                    r"|\bat\s+\d{1,2}\b"                            # "at 3"
                    r"|noon|midnight")                              # the two word times
    if not re.search(time_pattern, said):        # None of these patterns appear: no time was given.
        return {"success": False,
                "error": "The user has not said a time. Do not guess. Ask the user what time."}
    return None                                  # All good: the booking may go ahead.


def ask(user_text, on_sentence=None):
    """Run one user message through the agent. Calls on_sentence(text) for each finished sentence."""
    history.append({"role": "user", "content": user_text})
    t0 = time.perf_counter()                 # Stopwatch for the whole request.
    spoke_first = False                      # Have we said the first sentence yet?
    if ACK and on_sentence:                  # Speak the acknowledgement immediately, before the model answers.
        on_sentence(ACK)
        print(f"   [acknowledged after {time.perf_counter() - t0:.1f}s]")

    def emit(sentence):                      # Helper: pass a finished sentence to the speaker.
        nonlocal spoke_first
        if not spoke_first:
            print(f"   [first sentence ready after {time.perf_counter() - t0:.1f}s]")
            spoke_first = True
        if on_sentence:
            on_sentence(sentence)

    for _ in range(6):
        stream = ollama.chat(                # stream=True returns small chunks as they are generated.
            model=CHAT,
            messages=[{"role": "system", "content": system_prompt()}] + history,
            tools=list(TOOLS.values()),
            think=THINK,
            keep_alive=KEEP_ALIVE,
            options={"num_ctx": CONTEXT},
            stream=True,
        )
        content = ""                         # The full reply text, built up from chunks.
        buffer = ""                          # Text not yet spoken.
        tool_calls = []                      # Any tools the model asks for.

        for chunk in stream:                 # Each chunk is a few words.
            piece = chunk.message.content or ""
            content += piece
            buffer += piece
            if chunk.message.tool_calls:
                tool_calls.extend(chunk.message.tool_calls)
            while True:                      # Speak every complete sentence in the buffer.
                match = re.match(r"\s*(.+?[.!?])\s+", buffer, re.S)   # Text ending in . ! or ? plus a space.
                if not match:
                    break
                emit(match.group(1))
                buffer = buffer[match.end():]    # Remove what we just spoke.
        if buffer.strip():                   # The final sentence has no space after it, so flush it now.
            emit(buffer.strip())

        history.append(ollama.Message(role="assistant", content=content,
                                      tool_calls=tool_calls or None))   # Rebuild the full message from chunks.

        if not tool_calls:                   # No tools requested: this was the final reply.
            return content

        for call in tool_calls:              # Run the requested tools, same as before.
            name = call.function.name
            args = call.function.arguments
            func = TOOLS.get(name)
            problem = grounding_error(name, args)
            if func is None:
                result = {"success": False, "error": f"unknown tool {name}"}
            elif problem:
                result = problem
            else:
                try:
                    result = func(**args)
                except TypeError as error:
                    result = {"success": False, "error": str(error)}
            print(f"   [tool] {name}({args}) -> {result}")
            history.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})

    return "Sorry, I got stuck."


if __name__ == "__main__":
    while True:
        text = input("you> ").strip()
        if text in ("quit", "exit"):
            break
        if text == "stop":                   # Typing "stop" silences the voice at once.
            speech.stop()
            continue
        if text:
            print("loop>", ask(text, on_sentence=speech.speak))   # Each finished sentence goes to the speaker.
