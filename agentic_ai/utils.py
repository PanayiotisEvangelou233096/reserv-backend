"""Utility functions for restaurant planner"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from firebase_admin import firestore
from openai import OpenAI  
import numpy as np  

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Disable LangSmith tracing to avoid 403 errors
# If you want to enable it, make sure you have a valid LANGCHAIN_API_KEY in .env
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
# os.environ.setdefault("LANGCHAIN_PROJECT", "restaurant-planner")


# Cache LLM instances to avoid recreation
_llm_cache = {}


def _get_embedding_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url="https://fj7qg3jbr3.execute-api.eu-west-1.amazonaws.com/v1"
        )
    return _embedding_client


def _text_embedding(text: str) -> np.ndarray:
    """Return embedding for text, cached to avoid repeated API calls."""
    normalized = text.strip().lower()
    if not normalized:
        return np.array([], dtype=np.float32)

    if normalized in _embedding_cache:
        return _embedding_cache[normalized]

    client = _get_embedding_client()
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=normalized,
        )
    except Exception:
        # On failure cache empty vector to avoid repeated retries
        _embedding_cache[normalized] = np.array([], dtype=np.float32)
        return _embedding_cache[normalized]

    embedding = np.array(response.data[0].embedding, dtype=np.float32)
    _embedding_cache[normalized] = embedding
    return embedding


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0 or b.size == 0:
        return 0.0

    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def get_llm(
    model: str = "gpt-4.1-mini",
    temperature: float = 0,
    max_tokens: int = 500,
) -> ChatOpenAI:
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


def filter_blacklisted_restaurants(restaurants: list, dislikes: list) -> list:
    """Filter out blacklisted restaurants before scoring
    Returns filtered list of restaurants"""
    if not dislikes:
        return restaurants
    
    # Build sets of blacklisted identifiers
    blacklisted_location_ids = set()
    blacklisted_restaurants = set()  # (name, address) tuples
    
    for dislike in dislikes:
        if dislike.get('is_active', True):
            # Check by location_id if available
            if 'location_id' in dislike:
                blacklisted_location_ids.add(dislike['location_id'])
            # Also check by name and address (for backwards compatibility)
            if 'restaurant_name' in dislike and 'restaurant_address' in dislike:
                blacklisted_restaurants.add((
                    dislike['restaurant_name'].lower().strip(),
                    dislike['restaurant_address'].lower().strip()
                ))
    
    # Filter restaurants
    filtered = []
    for restaurant in restaurants:
        is_blacklisted = False
        
        # Check by location_id (primary method)
        restaurant_location_id = restaurant.get('location_id')
        if restaurant_location_id and restaurant_location_id in blacklisted_location_ids:
            is_blacklisted = True
        
        # Check by name and address (fallback)
        if not is_blacklisted:
            restaurant_name = restaurant.get('name', '').lower().strip()
            restaurant_address_obj = restaurant.get('address_obj', {})
            if isinstance(restaurant_address_obj, dict):
                address_parts = [
                    restaurant_address_obj.get('street', ''),
                    restaurant_address_obj.get('city', ''),
                    restaurant_address_obj.get('state', ''),
                    restaurant_address_obj.get('country', '')
                ]
                restaurant_address = ', '.join(filter(None, address_parts)).lower().strip()
            else:
                restaurant_address = str(restaurant_address_obj).lower().strip() if restaurant_address_obj else ''
            
            if (restaurant_name, restaurant_address) in blacklisted_restaurants:
                is_blacklisted = True
        
        if not is_blacklisted:
            filtered.append(restaurant)
    
    return filtered


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

