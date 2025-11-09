"""Restaurant Planner LangGraph Workflow"""
from langgraph.graph import StateGraph, END, START
from typing import TypedDict, List, Literal, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime

from .models import ParsedInput, Restaurant, RestaurantRecommendation
from .utils import get_llm, get_restaurants_from_firestore, score_restaurant


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


def parse_input(state: RestaurantPlannerState) -> RestaurantPlannerState:
    """Parse combined text input into structured parameters - optimized for speed"""
    combined_input = state.get("input")
    if not combined_input:
        return state
    
    # Use faster model (gpt-4o-mini) instead of reasoning model (gpt-5-nano)
    # Limit max_tokens to prevent excessive generation (300 is enough for structured output)
    llm = get_llm(model="gpt-4.1-nano", temperature=0, max_tokens=4000).with_structured_output(ParsedInput)
    
    # Concise prompt to reduce input tokens and speed up processing
    prompt = """Extract restaurant booking details:
    - attendee_count: number of people
    - location_preference: location/area
    - time_preference: preferred time
    - date: preferred date
    - budget_min: minimum per person (or null)
    - budget_max: maximum per person (or null)
    - dietary_restrictions: all restrictions combined (or "")
    - cuisine_preferences: list of cuisines

    If budgets vary, use range covering all. If cuisines vary, include all."""
    
    parsed = llm.invoke([
        SystemMessage(content=prompt),
        HumanMessage(content=combined_input)
    ])
    
    return {
        **state,
        "attendee_count": parsed.attendee_count,
        "location_preference": parsed.location_preference,
        "time_preference": parsed.time_preference,
        "date": parsed.date,
        "budget_min": parsed.budget_min or 0,
        "budget_max": parsed.budget_max or 1000,
        "dietary_restrictions": parsed.dietary_restrictions or "No restrictions",
        "cuisine_preferences": parsed.cuisine_preferences or ["Any"],
        "messages": state.get("messages", []) + [
            f"Parsed: {parsed.attendee_count} attendees, "
            f"{parsed.location_preference}, {parsed.time_preference}, "
            f"Budget: ${parsed.budget_min or 0}-${parsed.budget_max or 0}"
        ]
    }


def discover_restaurants(state: RestaurantPlannerState) -> RestaurantPlannerState:
    """Discover and rank restaurants based on parsed criteria"""
    # Get all restaurants from Firestore
    restaurants = get_restaurants_from_firestore()
    
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
    
    return {
        **state,
        "restaurant_candidates": restaurants,
        "top_recommendations": recommendations,
        "messages": state.get("messages", []) + [
            f"Found {len(restaurants)} restaurants, selected top 5 matches"
        ]
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