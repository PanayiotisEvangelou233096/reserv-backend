"""Utility functions for restaurant planner"""
import os
from typing import Dict

import numpy as np
from dotenv import load_dotenv
from firebase_admin import firestore
from langchain_openai import ChatOpenAI
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
)

# Disable LangSmith tracing to avoid 403 errors
# Enable only when a valid LANGCHAIN_API_KEY is configured.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
# os.environ.setdefault("LANGCHAIN_PROJECT", "restaurant-planner")


# Cache LLM instances to avoid recreation
_llm_cache: Dict[tuple[str, float, int], ChatOpenAI] = {}
_embedding_client: OpenAI | None = None
_embedding_cache: Dict[str, np.ndarray] = {}


def _get_embedding_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(api_key=OPENAI_API_KEY)
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
    model: str = "gpt-4o-mini",
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
            base_url=(
                "https://fj7qg3jbr3.execute-api.eu-west-1.amazonaws.com/v1"
            ),
            max_tokens=max_tokens,
            timeout=30,  # Add timeout to prevent hanging
        )
    return _llm_cache[cache_key]


def get_restaurants_from_firestore() -> list:
    """Fetch all restaurants from Firestore"""
    db = firestore.client()
    restaurants = []
    for doc in db.collection('restaurants').stream():
        restaurants.append(doc.to_dict())
    return restaurants


def score_restaurant(
    restaurant: dict,
    parsed_input: dict,
) -> tuple[float, str]:
    """Score a restaurant based on parsed input criteria
    Returns tuple of (score, reasoning)"""
    score = 0.0
    reasons = []

    # Location match
    address_obj = restaurant.get("address_obj", {})
    city = ""
    if isinstance(address_obj, dict):
        city = address_obj.get("city", "")
    location_pref = parsed_input.get("location_preference", "")
    if city and location_pref.lower() in city.lower():
        score += 2.0
        reasons.append(f"Location matches {location_pref}")

    # Cuisine match via embeddings (with keyword fallback)
    restaurant_cuisines = restaurant.get("cuisine", []) or []
    parsed_cuisines = parsed_input.get("cuisine_preferences", []) or []
    if (
        restaurant_cuisines
        and parsed_cuisines
        and "Any" not in parsed_cuisines
    ):
        restaurant_text = ", ".join(restaurant_cuisines)
        preference_text = ", ".join(parsed_cuisines)

        rest_embedding = _text_embedding(f"restaurant:{restaurant_text}")
        pref_embedding = _text_embedding(f"user:{preference_text}")
        cuisine_similarity = _cosine_similarity(rest_embedding, pref_embedding)

        if cuisine_similarity > 0:
            # Weight similarity to keep overall score within a comparable range
            score += cuisine_similarity * 3.0
            reasons.append(
                "Cuisine similarity "
                f"{cuisine_similarity:.2f} for preferences {preference_text}"
            )
        else:
            # Fallback to keyword overlap
            matching_cuisines = (
                set(c.lower() for c in restaurant_cuisines)
                & set(c.lower() for c in parsed_cuisines)
            )
            if matching_cuisines:
                score += len(matching_cuisines)
                reasons.append(
                    "Matches cuisines: "
                    f"{', '.join(matching_cuisines)}"
                )

    # Budget match (using price_level as proxy)
    price_levels = {"$": 25, "$$": 50, "$$$": 100, "$$$$": 200}
    rest_price = price_levels.get(restaurant.get("price_level", "$$"), 50)
    budget_min = parsed_input.get("budget_min", 0)
    budget_max = parsed_input.get("budget_max", 1000)
    if budget_min <= rest_price <= budget_max:
        score += 1.5
        reasons.append(
            "Price level "
            f"{restaurant.get('price_level', '$$')} within budget range"
        )

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