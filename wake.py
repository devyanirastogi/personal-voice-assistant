import re                                    # Pattern matching.
import tomllib
from pathlib import Path

WORDS = tomllib.loads(Path("config.toml").read_text())["wake"]["words"]   # The wake word spellings.
WORD_PATTERN = "|".join(re.escape(w) for w in WORDS)    # Joins them as: loop|loops|loupe|...

# "Set off" means: start of text, OR just after punctuation, OR just after okay/hey.
PATTERN = re.compile(
    r"(?:^|(?<=[,.!?;:])\s*|\b(?:okay|ok|hey|hi)\b[,\s]+)"   # What may come right before the wake word.
    rf"\b({WORD_PATTERN})\b[,.!?;:]*",                        # The wake word itself, plus trailing punctuation.
    re.IGNORECASE,
)


def extract_command(text):
    """Return (heard_wake_word, command). The command is the text with the wake word removed."""
    match = PATTERN.search(text.strip())     # Look for the wake word anywhere in the text.
    if not match:
        return False, ""                     # No wake word: ignore this speech.
    rest = text[:match.start()] + " " + text[match.end():]   # Everything except the wake word.
    rest = re.sub(r"^[\s,.!?;:]+", "", rest.strip())         # Tidy leading punctuation and spaces.
    return True, rest.strip()