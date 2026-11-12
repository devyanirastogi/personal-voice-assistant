import tomllib 
from pathlib import Path
import ollama 

# Read settings from config.toml
config = tomllib.loads(Path("config.toml").read_text())
CHAT = config["models"]["chat"] 

# Test 1: does the chat model answer? 
reply = ollama.chat(
    model = CHAT, 
    messages = [{"role": "user", "content": "Hello, how are you?"}])

print ("1. chat says:", reply.message.content)

# Test 2: does the model ask to use a tool? 
def get_weather(city:str) -> str:
    """Get the weather for the given city""" 
    return f"The weather in {city} is sunny."

reply = ollama.chat(
    model = CHAT, 
    messages = [{"role": "user", "content": "What is the weather in Chicago?"}],
    tools = [get_weather])

print ("2. tool calls:", reply.message.tool_calls) 

# Test 3: does the embedding model work?
EMBED = config["models"]["embed"]

result = ollama.embed(
    model = EMBED,
    input = "I prefer morning meetings", # sentence to convert to embedding
)
vector = result.embeddings[0] 

print ("3. embedding vector length:", len(vector))
print ("3. first 5 numbers:", vector[:5])

# Test 4: can we write to and read from a SQLite database? ---
import sqlite3                                    

Path("data").mkdir(exist_ok=True)                 
db = sqlite3.connect("data/_check.db")            

db.execute("DROP TABLE IF EXISTS test")          
db.execute("CREATE TABLE test (note TEXT)")       
db.execute("INSERT INTO test (note) VALUES (?)",  
           ("hello from sqlite",))                
db.commit()                                      # Save the change to the file

rows = db.execute("SELECT note FROM test").fetchall()   # Returns all the notes as a list
print("4. sqlite read:", rows)                    
db.close()

# Test 5: can we store a vector and find it again by meaning? 
import shutil                                          # Built-in tool for deleting folders
from qdrant_client import QdrantClient                 # The vector database client
from qdrant_client.models import Distance, VectorParams, PointStruct   

client = QdrantClient(path="data/_check_qdrant")       # Open a vector database stored in this folder (no server needed)

if client.collection_exists("test"):                   # If an old test collection exists...
    client.delete_collection("test")                   # ...delete it so reruns start clean

client.create_collection(                              
    collection_name="test",                            
    vectors_config=VectorParams(
        size=len(vector),                              # Each vector has 768 numbers (from test 3)
        distance=Distance.COSINE,                      # Measure closeness with cosine similarity
    ),
)

client.upsert(                                         # "Upsert" = insert, or update if the id exists
    collection_name="test",
    points=[PointStruct(                               # A "point" is one saved item
        id=1,                                          
        vector=vector,                                 # Its embedding (from test 3: "I prefer morning meetings")
        payload={"text": "I prefer morning meetings"}, # The original text, saved next to the vector.
    )],
)

question = "what time of day do I like meetings?"      # A question that shares almost no words with the memory
question_vector = ollama.embed(model=EMBED, input=question).embeddings[0]   # Embed the question as well

hit = client.query_points(                             # Search: find the closest saved vector
    collection_name="test",
    query=question_vector,                            
    limit=1,                                           # Return only the best match
).points[0]                                            # Take the first (best) result out of the list

print("5. found:", hit.payload["text"])                # The text of the memory it found
print("5. similarity score:", round(hit.score, 2))     # How close the match is (1 = identical)

client.close()                                         
shutil.rmtree("data/_check_qdrant")                    
import os; os.remove("data/_check.db")                 

