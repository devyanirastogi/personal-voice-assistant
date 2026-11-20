# Loop: a local voice assistant

Loop is a voice assistant that runs entirely on my laptop. I say
"Loop, book a dentist appointment tomorrow at 3 PM in Chicago" and it books it,
answers out loud, and remembers things about me. A web page shows what it
heard, what it did, and what it remembers. No cloud services are used.

Built for macOS on Apple Silicon (it uses the built-in `say` voice).

## How it works

```
mic -> speech to text (Whisper) -> wake word -> agent (tools + memory)
    -> text to speech -> speaker
                          |
              appointments (SQLite), memory (Qdrant)
```

## Setup

1. Install [Ollama](https://ollama.com) and pull the models:
   ```
   ollama pull qwen3.5:4b
   ollama pull nomic-embed-text
   ```
2. Install the packages (Python 3.11):
   ```
   python -m pip install -r requirements.txt
   ```
3. Allow microphone access for your terminal or VS Code when macOS asks.
4. Check that the models and stores work: `python setup_check.py`

## Run

- Web page and voice together: `streamlit run app.py`
- Voice only, in the terminal: `python voice.py`
- Typed test chat: `python agent.py`
- Eight-check benchmark: `python benchmark.py` (or `python benchmark.py llama3.2:3b`).
  Warning: it deletes the saved appointments first.

Say the wake word first: "Loop, what is on my calendar?"

## Settings

Everything is in `config.toml`: model names, voice, wake word spellings,
silence length, memory settings, and file paths. Change the model there to
compare models.

## Files

| File | What it does |
|---|---|
| `db.py` | Saves and reads appointments (SQLite) |
| `tools.py` | The tools the model can call, with input checks |
| `agent.py` | The agent loop, system prompt and safety checks |
| `speech.py` | Speaks sentences as they arrive; can stop instantly |
| `audio_in.py` | Listens to the mic and cuts speech into utterances |
| `stt.py` | Speech to text with Whisper |
| `wake.py` | Finds the wake word in the text |
| `memory.py` | Long-term memory searched by meaning |
| `voice.py` | The always-on listening loop (runs in a background thread) |
| `app.py` | The Streamlit web page |

## What I learned

Small models guess. My 4B model made up a location, skipped the delete
confirmation, and left out the appointment id. Asking nicely in the prompt was
not enough, so I added code checks: a booking is blocked unless the user really
said the location, time and day, and a delete is blocked until the user says
"yes".

## Results

**Stage 1 (typed):** 8 of 8 checks passed.

**Stage 3 (spoken):** 8 of 8 worked, across two runs. Things that went wrong:

- Whisper heard "dentist" as "renders" (`"Delete my renders appointment."`).
- It heard "Let's do it." instead of "yes", so it was ignored.
- "I like to loop videos" came out as `"videos."` because the start was clipped.
  I fixed this by only throwing away buffered audio after Loop speaks.
- A plain "Yes." with no wake word was ignored even though it was inside the
  8-second follow-up window. I did not find the cause. Saying "Loop, yes" works.

**Stage 4 (memory):** I said "remember that I prefer morning meetings",
restarted, and asked "what time of day do I prefer for meetings". It answered
"You prefer morning meetings."

**Stage 6 (measured, typed):**

| Model | Checks passed (of 8) | Total seconds for the eight checks |
|---|---|---|
| qwen3.5:4b (default) | 8 (script scored 7) | 89.2 |
| llama3.2:3b | 7 (script scored 3) | 39.2 |

For qwen, the script's check 3 wanted a literal "?" in the reply, which was too
strict (the agent did ask where and saved nothing). For llama, only check 3
failed on its own: it booked the haircut in Chicago, reusing the place from an
earlier message. Checks 5 to 8 failed in the script only because that extra
haircut stayed in the database. llama was about 2.3x faster but less accurate.

The biggest source of mistakes was the small models guessing values the user
never gave, and I fixed it by moving those rules out of the prompt into code
checks that block a booking or delete until the user has actually said the
location, time, day or "yes". The weak spot that remains is that the check looks
at the last three messages, so llama reused "Chicago" from an earlier turn.

## Known limits

- The first words you hear are a short "Okay." that plays right away. The real
  answer comes about 6 to 15 seconds later (two model calls per command).
- The follow-up window bug described above.
- The model can still make small mistakes, so check the appointment list on the
  web page.
- Qdrant's on-disk mode allows only one program to open the memory folder at a
  time.
