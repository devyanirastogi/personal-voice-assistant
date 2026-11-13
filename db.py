import sqlite3
import tomllib 
from pathlib import Path # Handles file paths in a cross-platform way

config = tomllib.loads(Path("config.toml").read_text())
DB_PATH = config["paths"]["appointments_db"] # Path to the SQLite database file 

def _connect():
    """Open the database and make sure the appointments table exists."""
    Path(DB_PATH).parent.mkdir(exist_ok=True) # Make sure the folder exists
    db = sqlite3.connect(DB_PATH)              # Open the database file
    db.row_factory = sqlite3.Row  # Return rows as dictionaries instead of tuples
    db.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        location TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT ''
    )""")  # Create the table if it doesn't exist
    return db

def add_appointment(date, location, title, description=""):
    """Save one appointment and return its new id."""
    db = _connect() # Connect to the database
    cursor = db.execute("""
        INSERT INTO appointments (date, location, title, description)
        VALUES (?, ?, ?, ?)
    """, (date, location, title, description))
    db.commit()  # Save the change to the file
    new_id = cursor.lastrowid  # Get the id of the new row 
    db.close()
    return new_id 

def get_appointments():
    """Return all appointments as a list of dictionaries, earliest first."""
    db = _connect() # Connect to the database
    rows = db.execute("SELECT * FROM appointments ORDER BY date ASC").fetchall() # Get all rows
    db.close()
    return [dict(row) for row in rows] # Convert each row to a dictionary

def get_appointment(appointment_id):
    """Return one appointment as a dictionary, or None if not found."""
    db = _connect() # Connect to the database
    row = db.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,)).fetchone() # Get one row or none if not found
    db.close()
    return dict(row) if row else None # Convert to dictionary if found, else return None

ALLOWED_FIELDS = {"date", "location", "title", "description"} # Fields that can be updated

def change_appointment(appointment_id, **fields):   
    """Change only the fields given. Return True if an appointment was updated""" 
    changes = {name: value for name, value in fields.items() 
               if name in ALLOWED_FIELDS and value is not None} # Only keep allowed fields with non-None values 
    if not changes:  # If no valid fields were provided, return False
        return False
    set_clause = ", ".join(f"{name} = ?" for name in changes) # Create the SET clause for the SQL statement 
    db = _connect() # Connect to the database
    cursor = db.execute(f"UPDATE appointments SET {set_clause} WHERE id = ?", 
                        (*changes.values(), appointment_id)) # Execute the update with the new values and the appointment id 
    db.commit()  # Save the change to the file
    updated = cursor.rowcount > 0 # Check if any row was updated
    db.close() 
    return updated

def remove_appointment(appointment_id):
    """Delete one appointment. Return True if an appointment was deleted."""
    db = _connect() # Connect to the database
    cursor = db.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,)) # Execute the delete statement
    db.commit()  # Save the change to the file
    deleted = cursor.rowcount > 0 # Check if any row was deleted
    db.close()
    return deleted

