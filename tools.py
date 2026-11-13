from datetime import datetime
import db # Refers to the db.py file in this folder, which contains functions for storing and retrieving appointments

def _check_date(text):
    """Return True if the text looks like "YYYY-MM-DD HH:MM" ."""
    try:
        datetime.strptime(text, "%Y-%m-%d %H:%M") # Try to parse the date string
        return True
    except (ValueError, TypeError): # If parsing fails, it's not a valid date
        return False

def create_appointment(date: str, location: str, title: str, description: str = "") -> dict:
    """Save a new appointment and return its id.

    Args:
        date: When the appointment is, as YYYY-MM-DD HH:MM in 24-hour time, e.g. 2026-11-13 15:00.
        location: Where it takes place, e.g. Chicago. Never guess this; ask the user if unknown.
        title: Short name of the appointment, e.g. Dentist.
        description: Optional extra details.
    """
    if not _check_date(date):                        # Reject a badly formatted date
        return {"success": False, "error": "date must look like YYYY-MM-DD HH:MM"}
    if not location or not location.strip():         # Reject an empty location.
        return {"success": False, "error": "location is required; ask the user"}
    new_id = db.add_appointment(date, location.strip(), title, description)   # Save it and get its id
    return {"success": True, "id": new_id}           # Report success with the real id


def list_appointments() -> dict:
    """Return all saved appointments, ordered by date, each with its id."""
    return {"success": True, "appointments": db.get_appointments()}   # Everything in the database


def update_appointment(appointment_id: int, date: str = "", location: str = "",
                       title: str = "", description: str = "") -> dict:
    """Change only the fields given on an existing appointment.

    Args:
        appointment_id: The id of the appointment to change (from list_appointments).
        date: New date as YYYY-MM-DD HH:MM, or leave empty to keep the current one.
        location: New location, or leave empty to keep the current one.
        title: New title, or leave empty to keep the current one.
        description: New description, or leave empty to keep the current one.
    """
    appointment_id = int(appointment_id)             # Models sometimes send "3" instead of 3; convert
    if date and not _check_date(date):               # Only check the date if one was given
        return {"success": False, "error": "date must look like YYYY-MM-DD HH:MM"}
    ok = db.change_appointment(                      # Empty strings become None, meaning "don't change"
        appointment_id,
        date=date or None, location=location or None,
        title=title or None, description=description or None,
    )
    if not ok:                                       # No row changed: wrong id or nothing to change
        return {"success": False, "error": f"no appointment with id {appointment_id}"}
    return {"success": True, "appointment": db.get_appointment(appointment_id)}   # Show the new state


def delete_appointment(appointment_id: int) -> dict:
    """Delete one appointment by id. Only call this after the user has said yes.

    Args:
        appointment_id: The id of the appointment to delete.
    """
    appointment_id = int(appointment_id)             # Same conversion as above
    if db.remove_appointment(appointment_id):        # True only if a row really was deleted
        return {"success": True, "deleted_id": appointment_id}
    return {"success": False, "error": f"no appointment with id {appointment_id}"}


if __name__ == "__main__":                           # Quick manual test: python tools.py
    print(create_appointment("2026-11-13 15:00", "Chicago", "Dentist"))   # Should succeed
    print(create_appointment("2026-11-13 15:00", "", "Dentist"))          # Should fail: no location
    print(create_appointment("tomorrow at 3", "Chicago", "Dentist"))      # Should fail: bad date
    print(list_appointments())