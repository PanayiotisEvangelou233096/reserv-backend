"""Utility functions for restaurant planner"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from firebase_admin import firestore

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Disable LangSmith tracing to avoid 403 errors
# If you want to enable it, make sure you have a valid LANGCHAIN_API_KEY in .env
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
# os.environ.setdefault("LANGCHAIN_PROJECT", "restaurant-planner")


# Cache LLM instances to avoid recreation
_llm_cache = {}

def get_llm(model: str = "gpt-4o-mini", temperature: float = 0, max_tokens: int = 500) -> ChatOpenAI:
    """Get LLM client with standard configuration - optimized for speed"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    # Use cache key to reuse instances
    cache_key = (model, temperature, max_tokens)
    if cache_key not in _llm_cache:
        _llm_cache[cache_key] = ChatOpenAI(
            model=model,
            temperature=temperature,
            api_key=OPENAI_API_KEY,
            base_url="https://fj7qg3jbr3.execute-api.eu-west-1.amazonaws.com/v1",
            max_tokens=max_tokens,
            timeout=30  # Add timeout to prevent hanging
        )
    return _llm_cache[cache_key]


def get_restaurants_from_firestore() -> list:
    """Fetch all restaurants from Firestore"""
    db = firestore.client()
    restaurants = []
    for doc in db.collection('restaurants').stream():
        restaurants.append(doc.to_dict())
    return restaurants


def score_restaurant(restaurant: dict, parsed_input: dict) -> tuple[float, str]:
    """Score a restaurant based on parsed input criteria
    Returns tuple of (score, reasoning)"""
    score = 0.0
    reasons = []

    # Location match
    address_obj = restaurant.get("address_obj", {})
    city = address_obj.get("city", "") if isinstance(address_obj, dict) else ""
    if city and parsed_input.get("location_preference", "").lower() in city.lower():
        score += 2.0
        reasons.append(f"Location matches {parsed_input['location_preference']}")
    
    # Cuisine match
    restaurant_cuisines = restaurant.get("cuisine", []) or []
    parsed_cuisines = parsed_input.get("cuisine_preferences", []) or []
    if restaurant_cuisines and parsed_cuisines and "Any" not in parsed_cuisines:
        matching_cuisines = set(c.lower() for c in restaurant_cuisines) & set(c.lower() for c in parsed_cuisines)
        if matching_cuisines:
            score += len(matching_cuisines)
            reasons.append(f"Matches cuisines: {', '.join(matching_cuisines)}")

    # Budget match (using price_level as proxy)
    price_levels = {"$": 25, "$$": 50, "$$$": 100, "$$$$": 200}
    rest_price = price_levels.get(restaurant.get("price_level", "$$"), 50)
    budget_min = parsed_input.get("budget_min", 0)
    budget_max = parsed_input.get("budget_max", 1000)
    if budget_min <= rest_price <= budget_max:
        score += 1.5
        reasons.append(f"Price level {restaurant.get('price_level', '$$')} within budget range")

    # Rating bonus
    rating = restaurant.get("rating", 0.0)
    if rating > 0:
        score += rating / 2  # Convert 5-star rating to 2.5 max bonus
        reasons.append(f"Rating bonus: {rating}/5 stars")
    
    # Size accommodation
    # Assuming restaurants can handle groups up to 20 by default
    attendee_count = parsed_input.get("attendee_count", 0)
    if attendee_count <= 20:
        score += 1.0
        reasons.append(f"Can accommodate group of {attendee_count}")

    # Ensure we have at least some reasoning
    if not reasons:
        reasons.append("General recommendation")

    reasoning = " | ".join(reasons)
    return score, reasoning