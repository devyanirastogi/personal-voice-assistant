import json                                  # Turns tool results (dictionaries) into text for the model.
import tomllib                               # Reads config.toml.
from datetime import datetime                # Gives us the current date and time.
from pathlib import Path
import ollama                                # Talks to the local model.
import tools                                 # Your four appointment tools
import time
import re                                        # Regular expressions, for pattern matching in text.

config = tomllib.loads(Path("config.toml").read_text())   # Load settings.
CHAT = config["models"]["chat"]              # Which chat model to use.
THINK = config["models"].get("think", False) # Whether the model reasons silently first (default: no).
KEEP_ALIVE = config["models"].get("keep_alive", "5m")   # How long Ollama keeps the model loaded after a call.
CONTEXT = config["models"].get("context", 4096)         # How many tokens the model can see at once.

# A lookup table: tool name -> the real Python function.
TOOLS = {f.__name__: f for f in [
    tools.create_appointment, tools.list_appointments,
    tools.update_appointment, tools.delete_appointment,
]}

history = []                                 # The conversation so far. Kept between turns so "move it" works.


def system_prompt():
    """Build the rules for the model. Rebuilt every request so the date is always current."""
    now = datetime.now().strftime("%A, %Y-%m-%d %H:%M")   # e.g. "Thursday, 2026-11-12 14:05".
    return f"""You are Loop, a voice assistant that manages the user's appointments.
The current date and time is {now}. Work out dates like "tomorrow" or "Friday" from this.
Rules:
- If the date, the time, or the location is missing or unclear (for example "at 3" with no AM or PM), ask one short question. Never guess or invent them.
- Never say something was booked, moved or deleted unless the tool just returned success. Read the id from the tool result.
- To delete: first find the appointment, ask the user to confirm with yes or no, and call delete only after they say yes.
- Reply in one or two short sentences. No lists, no markdown, because your reply will be spoken aloud.
- Answer only what was asked. Do not add extra questions or offers."""

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


def ask(user_text):
    """Send one user message through the agent loop and return the final reply text."""
    history.append({"role": "user", "content": user_text})    # Add what the user said.

    for _ in range(6):                       # At most 6 rounds, so a confused model can't loop forever
        started = time.perf_counter()        # For timing how long the model takes to answer.
        response = ollama.chat(
            model=CHAT,
            messages=[{"role": "system", "content": system_prompt()}] + history,   # Rules first, then the chat.
            tools=list(TOOLS.values()),      # The menu of tools the model may request.
            think=THINK,
            keep_alive=KEEP_ALIVE,
            options = {"num_ctx": CONTEXT},  # How many tokens the model can see at once.
        )
        print (f"   [model call took {time.perf_counter() - started:.1f}s]")  # Show how long the model took to answer
        message = response.message           # The model's answer: either text or tool requests.
        history.append(message)              # Remember it.

        if not message.tool_calls:           # No tool requested, so this is the final text reply.
            return message.content

        for call in message.tool_calls:      # The model asked for one or more tools.
            name = call.function.name        # Which tool.
            args = call.function.arguments   # With which arguments (a dictionary).
            func = TOOLS.get(name)           # Find the real function.
            problem = grounding_error(name, args)  # Check if the model is trying to use values the user never said.
            if func is None:                 # The model invented a tool that doesn't exist.
                result = {"success": False, "error": f"unknown tool {name}"}
            elif problem:
                result = problem              # The model is trying to book with values the user never said.
            else:
                try:
                    result = func(**args)    # RUN the tool. ** unpacks the dictionary into arguments.
                except TypeError as error:   # The model passed wrong or missing arguments.
                    result = {"success": False, "error": str(error)}
            print(f"   [tool] {name}({args}) -> {result}")   # Show what happened, so we can see for ourselves.
            history.append({"role": "tool", "tool_name": name,
                            "content": json.dumps(result)})  # Send the result back to the model.
        # Loop again: the model now sees the tool results and decides what to say or do next.

    return "Sorry, I got stuck."


if __name__ == "__main__":                   # Typed chat for testing: python agent.py
    while True:
        text = input("you> ").strip()        # Read a line you type.
        if text in ("quit", "exit"):
            break
        if text:
            print("loop>", ask(text))        # Run it through the agent and print the reply.