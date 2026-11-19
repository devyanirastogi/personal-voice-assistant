import json
import threading                             # Background work, and a lock for safety.
import time
import tomllib
import uuid                                  # Makes unique ids for memories.
from pathlib import Path
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

config = tomllib.loads(Path("config.toml").read_text())
EMBED = config["models"]["embed"]            # Embedding model.
CHAT = config["models"]["chat"]              # Chat model, used for extracting facts.
KEEP_ALIVE = config["models"].get("keep_alive", "5m")
CONTEXT = config["models"].get("context", 4096)
MEMORY_DIR = config["paths"]["memory_dir"]   # Where Qdrant stores memories on disk.
TOP_K = config["memory"]["top_k"]            # How many memories to put in the prompt.
MIN_SCORE = config["memory"]["min_score"]    # Ignore matches less similar than this.
DUPLICATE_SCORE = config["memory"]["duplicate_score"]   # Treat matches this similar as already known.
COLLECTION = "memories"

_lock = threading.Lock()                     # Only one thread may touch Qdrant at a time.
_client = None                               # Opened on first use.


def _embed(text):
    """Turn text into its embedding vector (a list of 768 numbers)."""
    return ollama.embed(model=EMBED, input=text).embeddings[0]


def _get_client():
    """Open the memory database (once) and make sure the collection exists."""
    global _client
    if _client is None:
        Path(MEMORY_DIR).mkdir(parents=True, exist_ok=True)
        _client = QdrantClient(path=MEMORY_DIR)          # Stored on disk, so it survives restarts.
        if not _client.collection_exists(COLLECTION):
            _client.create_collection(
                COLLECTION,
                vectors_config=VectorParams(size=len(_embed("test")), distance=Distance.COSINE))
    return _client


def search(query, limit=TOP_K):
    """Return the stored facts most similar in meaning to the query."""
    if not query.strip():
        return []
    vector = _embed(query)
    with _lock:
        hits = _get_client().query_points(COLLECTION, query=vector, limit=limit).points
    return [h.payload["text"] for h in hits if h.score >= MIN_SCORE]   # Drop weak matches.


def remember(fact):
    """Save a fact unless a near-identical one exists. Return True if it was saved."""
    fact = fact.strip()
    if not fact:
        return False
    vector = _embed(fact)
    with _lock:
        client = _get_client()
        hits = client.query_points(COLLECTION, query=vector, limit=1).points
        if hits and hits[0].score >= DUPLICATE_SCORE:    # Already known: don't store it twice.
            return False
        client.upsert(COLLECTION, points=[PointStruct(
            id=str(uuid.uuid4()), vector=vector,
            payload={"text": fact, "created": time.strftime("%Y-%m-%d %H:%M")})])
    return True


def all_memories():
    """Return every stored memory (the web page will show these)."""
    with _lock:
        points, _ = _get_client().scroll(COLLECTION, limit=200, with_payload=True)
    return [{"text": p.payload["text"], "created": p.payload.get("created", "")} for p in points]


EXTRACT_PROMPT = """Extract lasting personal facts and preferences about the user from their message: name, likes, dislikes, habits, family, work, preferred times.
Do NOT extract appointments, bookings, specific dates or times of events, or requests and questions.
If the message contains no personal fact, return an empty list.
Write each fact as one short sentence starting with "The user"."""


def extract_facts(user_text):
    """Ask the chat model for personal facts in the text. Returns a list of strings."""
    response = ollama.chat(
        model=CHAT,
        messages=[{"role": "system", "content": EXTRACT_PROMPT},
                  {"role": "user", "content": user_text}],
        format={"type": "object",                           # Force the reply to be JSON like {"facts": [...]}.
                "properties": {"facts": {"type": "array", "items": {"type": "string"}}},
                "required": ["facts"]},
        think=False, keep_alive=KEEP_ALIVE, options={"num_ctx": CONTEXT},   # Same settings: no model reload.
    )
    try:
        facts = json.loads(response.message.content).get("facts", [])
    except (json.JSONDecodeError, AttributeError):
        return []
    return [f for f in facts if isinstance(f, str)]


def _extract_and_store(user_text):
    """Runs in the background: extract facts and save them."""
    try:
        for fact in extract_facts(user_text):
            if remember(fact):
                print(f"   [memory] saved: {fact}")
    except Exception as error:               # A background failure must never crash the assistant.
        print(f"   [memory] extraction failed: {error}")


def extract_in_background(user_text):
    """Start extraction in a background thread and return immediately."""
    threading.Thread(target=_extract_and_store, args=(user_text,), daemon=True).start()