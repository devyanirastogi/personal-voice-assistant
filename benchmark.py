import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import agent                                 # The agent loop.
import db                                    # To check what was really stored.

if len(sys.argv) > 1:                        # Optional: python benchmark.py <model name>
    agent.CHAT = sys.argv[1]                 # Swap the chat model for this run.
    agent.THINK = None                       # Don't send the "think" setting (not all models support it).
print("Model:", agent.CHAT)

Path(db.DB_PATH).unlink(missing_ok=True)     # WARNING: deletes your appointments so the test starts clean.
agent.history.clear()                        # Start a fresh conversation.
agent.warm_up()                              # Load the model first, so loading time isn't counted.

total = 0.0                                  # Seconds spent in the agent across all checks.
passed = 0                                   # How many checks passed.
tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")


def ask(text):
    """Send one typed command to the agent and add its duration to the total."""
    global total
    started = time.perf_counter()
    reply = agent.ask(text)
    total += time.perf_counter() - started
    return reply


def record(number, ok, text, reply):
    """Print and count one check result, along with what is really in the database."""
    global passed
    passed += bool(ok)
    print(f"{number}. {'PASS' if ok else 'FAIL'}  you: {text}\n   reply: {reply}\n   db: {db.get_appointments()}\n")


# 1 and 2: book the dentist appointment, and check the id appears in the reply.
text = "book a dentist appointment tomorrow at 3 pm in Chicago"
reply = ask(text)
rows = db.get_appointments()
ok = len(rows) == 1 and rows[0]["date"] == f"{tomorrow} 15:00" and "chicago" in rows[0]["location"].lower()
record(1, ok, text, reply)
first_id = rows[0]["id"] if rows else -1
record(2, rows and re.search(rf"\b{first_id}\b", reply), "(id in the reply above)", reply)

# 3: missing location: nothing saved, and the agent asks a question.
before = len(db.get_appointments())
text = "book a haircut on Friday at 10 am"
reply = ask(text)
record(3, len(db.get_appointments()) == before and "?" in reply, text, reply)

# 4: the calendar mentions the dentist appointment.
text = "what is on my calendar"
reply = ask(text)
record(4, "dentist" in reply.lower(), text, reply)

# 5: move it: same row, now 16:00, no duplicate.
text = "move my dentist appointment to 4 pm"
reply = ask(text)
rows = db.get_appointments()
record(5, len(rows) == 1 and rows[0]["id"] == first_id and rows[0]["date"].endswith("16:00"), text, reply)

# 6: delete asks first, and the row is still there.
text = "delete my dentist appointment"
reply = ask(text)
record(6, len(db.get_appointments()) == 1 and ("?" in reply or "yes" in reply.lower()), text, reply)

# 7: yes: the row is deleted.
text = "yes"
reply = ask(text)
record(7, len(db.get_appointments()) == 0, text, reply)

# 8: lunch with Sam: exactly one appointment, at Cafe Roma.
text = "book lunch with Sam on Friday at noon at Cafe Roma"
reply = ask(text)
rows = db.get_appointments()
record(8, len(rows) == 1 and "roma" in rows[0]["location"].lower(), text, reply)

print(f"RESULT  model={agent.CHAT}  checks passed: {passed} of 8  total seconds: {total:.1f}")