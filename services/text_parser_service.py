"""Service for parsing free text event descriptions"""
from agentic_ai.parse_free_text import parse_text_function

def parse_event_text(text: str) -> dict:
    """
    Parse free text event description into structured event data.
    
    Args:
        text: Free text description of the event
        
    Returns:
        dict: Structured event data with keys:
            - occasion
            - date
            - time 
            - location
            - dietary_restrictions
    """
    # Parse the text using the existing parser
    parsed = parse_text_function(text)
    
    # Convert to format expected by existing APIs
    # First, clean up the time format if needed
    time = parsed.get("time")
    if time and ":" not in time:
        # Convert descriptive times to 24-hour format
        time_mapping = {
            "morning": "09:00",
            "afternoon": "14:00",
            "evening": "19:00",
            "night": "20:00"
        }
        time = time_mapping.get(time.lower())  # Default to 7 PM if unknown

    # Handle number_of_attendees safely - subtract 1 if present, otherwise None
    number_of_attendees = parsed.get("number_of_attendees")
    expected_attendee_count = (number_of_attendees - 1) if number_of_attendees is not None else None
    
    formatted_data = {
        "location": parsed.get("location", ""),
        "occasion_description": parsed.get("occasion", ""),  # Changed to match expected key
        "expected_attendee_count": expected_attendee_count,  # Changed to match expected key
        "preferred_date": parsed.get("date"),
        "preferred_time_slots": [time] if time else [],
        "dietary_restrictions": parsed.get("dietary_restrictions", "").split(",") if parsed.get("dietary_restrictions") else [],
        "cuisine_preferences": parsed.get("cuisine_preferences", []),
        "budget_min": parsed.get("budget_min"),
        "budget_max": parsed.get("budget_max"),
        "extra_info": parsed.get("extra_info")
    }
    
    # Clean up the dietary restrictions - remove empty strings and whitespace
    if formatted_data["dietary_restrictions"]:
        formatted_data["dietary_restrictions"] = [
            r.strip() for r in formatted_data["dietary_restrictions"] if r.strip()
        ]
    
    return formatted_data