from wake import extract_command

cases = [                                    # (text, should the wake word be heard?)
    ("Loop, book a dentist appointment tomorrow at 3 PM in Chicago.", True),
    ("Okay, Loop, book a haircut on Friday.", True),
    ("Book a dentist appointment tomorrow at 3. Loop. Book it in Chicago.", True),
    ("Hey Loop what's on my calendar", True),
    ("Okay, Loop.", True),
    ("I like to loop videos.", False),
    ("I like loop videos.", False),
    ("Move my dentist appointment to 4 PM.", False),
]
for text, expected in cases:
    woke, command = extract_command(text)
    status = "PASS" if woke == expected else "FAIL"
    print(f"{status}  woke={woke!s:5}  command={command!r}   <- {text}")