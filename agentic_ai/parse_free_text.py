"""Free text parser for event information using LangGraph with tools"""
from langgraph.graph import StateGraph, END, START
from typing_extensions import TypedDict
from typing import Optional, Literal, List
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .utils import get_llm
from datetime import datetime


# Pydantic model for parsed output
class ParsedEventInfo(BaseModel):
    """Structured event information parsed from free text"""
    occasion: Optional[Literal["birthday party", "family meeting", "date", "friends meetup", "work meeting"]] = Field(
        default="meeting",
        description="Type of occasion: birthday party, family meeting, date, friends meetup, or work meeting"
    )
    date: Optional[str] = Field(
        default="today",
        description="Event date in YYYY-MM-DD format. Resolve relative dates like 'tomorrow', 'next Monday' using current time."
    )
    time: Optional[str] = Field(
        default=None,
        description="Event time in HH:MM format (24-hour) or descriptive (e.g., 'evening', 'afternoon')"
    )
    location: Optional[str] = Field(
        default=None,
        description="Event location or area aligned with the current location(e.g., 'Amsterdam Zuid', 'downtown', 'restaurant near Central Station')"
    )
    dietary_restrictions: Optional[str] = Field(
        default=None,
        description="CRITICAL: ALL dietary restrictions, allergies, intolerances, religious requirements, and medical dietary needs. MUST include: allergies (nuts, shellfish, dairy, eggs, soy, wheat, etc.), intolerances (lactose, gluten), religious (halal, kosher, vegetarian for religious reasons), medical (diabetes-friendly, low-sodium, etc.). Extract EVERYTHING mentioned, even casually. Format as comma-separated list. Leave empty ONLY if absolutely nothing is mentioned."
    )
    number_of_attendees: Optional[int] = Field(
        default=None,
        description="Number of attendees. Excluding the organizer."
    )
    cuisine_preferences: Optional[List[str]] = Field(
        default=None,
        description="List of cuisine preferences. General types only, not specific dishes. (e.g., Italian, Japanese, spicy food, vegetarian options, Mediterranean, etc.)"
    )
    budget_min: Optional[float] = Field(
        default=None,
        description="Minimum budget per person. Euro 1 to 1. None if range or no budget is mentioned."
    )
    budget_max: Optional[float] = Field(
        default=None,
        description="Maximum budget per person. Euros 1 to 1. None if range or no budget is mentioned."
    )
    extra_info: Optional[str] = Field(
        default=None,
        description="Additional information about the event. Concise and to the point. Interior, atmosphere, etc."
    )

# State for the parser graph
class ParserState(TypedDict):
    """State for free text parser workflow"""
    input_text: str
    parsed_info: Optional[dict]


def parse_text(state: ParserState) -> ParserState:
    """Parse free text using tools for context, then with_structured_output - optimized for speed"""
    input_text = state.get("input_text", "")
    
    if not input_text:
        return {**state, "parsed_info": {}}
    
    # Get current time directly (no tool invocation overhead)
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    current_day = now.strftime("%A")
    current_location = "Amsterdam"  # Default location
    
    # Use cached LLM with structured output to parse the text
    # Use faster model (gpt-4o-mini) instead of reasoning model (gpt-5-nano)
    # Limit max_tokens to prevent excessive generation (300 is enough for structured output)
    llm_structured = get_llm_structured()
    
    # Concise prompt to reduce input tokens and speed up processing
    system_prompt = """Extract event information from text. Use current time to resolve relative dates. Use the current location to align the event location(e.g., 'Amsterdam Zuid', 'Amsterdam city center', 'restaurant near Central Station'). Infer the occasion and number of attendees from the text(e.g., date is for 2).
    CRITICAL: Extract ALL dietary restrictions, allergies, intolerances, religious requirements, and medical needs. Missing any could cause serious health issues."""
        
    # Build concise prompt with current time context
    prompt = f"Time: {current_time} ({current_day}), Location: {current_location}\n\nInput: {input_text}"
    
    parsed = llm_structured.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])
    
    # Convert to dictionary
    parsed_info = parsed.model_dump(exclude_none=True)
    
    return {
        **state,
        "parsed_info": parsed_info
    }


# Cache the LLM structured output wrapper to avoid recreating it on every call
_cached_llm_structured = None

def get_llm_structured():
    """Get cached LLM with structured output - optimized for speed"""
    global _cached_llm_structured
    if _cached_llm_structured is None:
        # Use gpt-4 model for accurate parsing
        # Limit max_tokens to prevent excessive generation
        _cached_llm_structured = get_llm(model="gpt-4.1-nano", temperature=0, max_tokens=4000).with_structured_output(ParsedEventInfo)
    return _cached_llm_structured


# Build the parser graph
def build_parser_graph():
    """Build LangGraph workflow for parsing free text with tools"""
    workflow = StateGraph(ParserState)
    
    # Add node
    workflow.add_node("parse", parse_text)
    
    # Define edges
    workflow.add_edge(START, "parse")
    workflow.add_edge("parse", END)
    
    return workflow.compile()


# Create the graph instance
graph = build_parser_graph()


# Convenience function for direct parsing
def parse_text_function(input_text: str) -> dict:
    """
    Parse free text input into structured event information.
    
    Args:
        input_text: Free text containing event information
        
    Returns:
        Dictionary with keys: occasion, date, time, location, dietary_restrictions
    """
    state = {
        "input_text": input_text,
        "parsed_info": None
    }
    
    result = graph.invoke(state)
    return result.get("parsed_info", {})


if __name__ == "__main__":
    """Example usage"""
    # Test examples
    test_inputs = [
        "I want to organize a birthday party for next Monday at 7 PM in Amsterdam Zuid. Some guests are vegetarian. Around 20 bucks",
        "Work meeting tomorrow afternoon downtown, no dietary restrictions",
        "A date this Friday evening, location TBD, I'm allergic to nuts, 30-60 bucks",
        "Friends meetup next Saturday at 6 PM in the city center, vegetarian options needed"
    ]
    
    for test_input in test_inputs:
        print(f"\nInput: {test_input}")
        result = parse_text_function(test_input)
        print(f"Parsed: {result}")
        print("-" * 80)

