"""Restaurant Planner LangGraph Workflow"""
from langgraph.graph import StateGraph, END, START
from typing import TypedDict, List, Literal, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime

from .models import ParsedInput, Restaurant, RestaurantRecommendation
from .utils import get_llm, get_restaurants_from_firestore, score_restaurant, filter_blacklisted_restaurants


# Cache the LLM structured output wrapper to avoid recreating it on every call
_cached_llm_structured = None

def get_llm_structured():
    """Get cached LLM with structured output - optimized for speed"""
    global _cached_llm_structured
    if _cached_llm_structured is None:
        # Use gpt-4.1-nano model for accurate parsing
        # Limit max_tokens to prevent excessive generation
        _cached_llm_structured = get_llm(model="gpt-4.1-nano", temperature=0, max_tokens=1500).with_structured_output(ParsedInput)
    return _cached_llm_structured


class RestaurantPlannerState(TypedDict):
    """State for restaurant planning workflow"""
    input: Optional[str]  # Combined text input from all responses
    attendee_count: int
    location_preference: Optional[str]
    time_preference: Optional[str]
    date: Optional[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    dietary_restrictions: Optional[str]
    cuisine_preferences: List[str]
    restaurant_candidates: List[dict]
    top_recommendations: List[RestaurantRecommendation]
    current_attempt: int
    messages: List[str]
    dislikes: Optional[List[dict]]  # Blacklisted restaurants


def parse_input(state: RestaurantPlannerState) -> RestaurantPlannerState:
    """Parse combined text input into structured parameters - optimized for speed"""
    combined_input = state.get("input")
    if not combined_input:
        return state
    
    # Get current time directly (no tool invocation overhead)
    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    current_day = now.strftime("%A")
    current_location = "Amsterdam"  # Default location
    
    # Use cached LLM with structured output to parse the text
    llm_structured = get_llm_structured()
    
    # Concise system prompt with clear instructions
    system_prompt = """Extract restaurant booking details from combined attendee responses. Use current time to resolve relative dates and times. Use the current location to align the restaurant location preferences.
    
    CRITICAL INSTRUCTIONS:
    - Count ALL attendees including the organizer
    - Combine ALL dietary restrictions from ALL responses - missing any could cause serious health issues
    - Include ALL cuisine preferences from ALL responses
    - If budgets vary, use range covering all (lowest min, highest max)
    - Resolve relative dates/times using current time context
    - Align location preferences with current location context"""
    
    # Build concise prompt with current time context
    prompt = f"Time: {current_time} ({current_day}), Location: {current_location}\n\nCombined attendee responses:\n{combined_input}"
    
    parsed = llm_structured.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ])
    
    return {
        **state,
        "attendee_count": parsed.attendee_count,
        "location_preference": parsed.location_preference or "Amsterdam",
        "time_preference": parsed.time_preference or "evening",
        "date": parsed.date or now.strftime("%Y-%m-%d"),
        "budget_min": parsed.budget_min or 0,
        "budget_max": parsed.budget_max or 1000,
        "dietary_restrictions": parsed.dietary_restrictions or "No restrictions",
        "cuisine_preferences": parsed.cuisine_preferences or ["Any"],
        "messages": state.get("messages", []) + [
            f"Parsed: {parsed.attendee_count} attendees, "
            f"{parsed.location_preference or 'Amsterdam'}, {parsed.time_preference or 'evening'}, "
            f"Budget: €{parsed.budget_min or 0}-€{parsed.budget_max or 1000}"
        ]
    }


def discover_restaurants(state: RestaurantPlannerState) -> RestaurantPlannerState:
    """Discover and rank restaurants based on parsed criteria"""
    # Get all restaurants from Firestore
    all_restaurants = get_restaurants_from_firestore()
    
    # Filter out blacklisted restaurants BEFORE scoring
    dislikes = state.get("dislikes", [])
    restaurants = filter_blacklisted_restaurants(all_restaurants, dislikes)
    
    filtered_count = len(all_restaurants) - len(restaurants)
    if filtered_count > 0:
        filter_message = f"Filtered out {filtered_count} blacklisted restaurant(s)"
    else:
        filter_message = None
    
    # Score and rank restaurants
    scored_restaurants = []
    for restaurant in restaurants:
        score, reasoning = score_restaurant(restaurant, state)
        scored_restaurants.append((score, restaurant, reasoning))
    
    # Sort by score descending and take top 5
    scored_restaurants.sort(reverse=True, key=lambda x: x[0])
    top_5 = scored_restaurants[:5]
    
    # Convert to RestaurantRecommendation objects
    recommendations = [
        RestaurantRecommendation(
            restaurant=Restaurant(**rest),
            score=score,
            reasoning=reasoning
        )
        for score, rest, reasoning in top_5
    ]
    
    messages = state.get("messages", [])
    if filter_message:
        messages.append(filter_message)
    messages.append(f"Found {len(restaurants)} restaurants, selected top 5 matches")
    
    return {
        **state,
        "restaurant_candidates": restaurants,
        "top_recommendations": recommendations,
        "messages": messages
    }


# Build workflow
workflow = StateGraph(RestaurantPlannerState)
workflow.add_node("parse", parse_input)
workflow.add_node("discover", discover_restaurants)

workflow.add_edge(START, "parse")
workflow.add_edge("parse", "discover")
workflow.add_edge("discover", END)

app = workflow.compile()
graph = app