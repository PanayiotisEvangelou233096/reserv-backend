"""Data models for restaurant planning system"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ParsedInput(BaseModel):
    """Parsed input from combined text - all responses in one"""
    attendee_count: int = Field(
        description="Total number of people attending the event. Count all attendees including the organizer."
    )
    location_preference: Optional[str] = Field(
        default=None,
        description="Preferred location or area for the restaurant (e.g., 'Amsterdam Zuid', 'downtown', 'near Central Station'). Align with current location context if mentioned."
    )
    time_preference: Optional[str] = Field(
        default=None,
        description="Preferred time for dining in HH:MM format (24-hour) or descriptive (e.g., 'evening', 'lunch', '19:00'). Use current time to resolve relative times like 'tonight', 'this evening'."
    )
    date: Optional[str] = Field(
        default=None,
        description="Preferred date in YYYY-MM-DD format. Resolve relative dates like 'today', 'tomorrow', 'next Monday' using current time context."
    )
    budget_min: Optional[float] = Field(
        default=None,
        description="Minimum budget per person in Euros. Extract from ranges or single values. If multiple budgets mentioned, use the lowest. None if no budget mentioned."
    )
    budget_max: Optional[float] = Field(
        default=None,
        description="Maximum budget per person in Euros. Extract from ranges or single values. If multiple budgets mentioned, use the highest. None if no budget mentioned."
    )
    dietary_restrictions: Optional[str] = Field(
        default=None,
        description="CRITICAL: ALL dietary restrictions, allergies, intolerances, religious requirements, and medical dietary needs from ALL attendees. MUST include: allergies (nuts, shellfish, dairy, eggs, soy, wheat, etc.), intolerances (lactose, gluten), religious (halal, kosher, vegetarian for religious reasons), medical (diabetes-friendly, low-sodium, etc.). Combine all restrictions from all responses. Format as comma-separated list. Missing any could cause serious health issues. Leave empty ONLY if absolutely nothing is mentioned."
    )
    cuisine_preferences: Optional[List[str]] = Field(
        default=None,
        description="List of ALL cuisine preferences from ALL attendees. General types only, not specific dishes (e.g., 'Italian', 'Japanese', 'Mediterranean', 'vegetarian options', 'spicy food'). Include all unique preferences mentioned across all responses. Empty list if none mentioned."
    )


class Restaurant(BaseModel):
    """Restaurant model matching Firestore schema"""
    location_id: str = Field(default="")
    name: str
    description: str = Field(default="")
    web_url: str = Field(default="")
    address_obj: dict = Field(default_factory=dict)
    latitude: float = Field(default=0.0)
    longitude: float = Field(default=0.0)
    email: str = Field(default="")
    phone: str = Field(default="")
    website: str = Field(default="")
    ranking_data: str = Field(default="")
    rating: float = Field(default=0.0)
    num_reviews: int = Field(default=0)
    review_rating_count: dict = Field(default_factory=dict)
    price_level: str = Field(default="$$")
    hours: dict = Field(default_factory=dict)
    cuisine: List[str] = Field(default_factory=list)

    class Config:
        # Allow extra fields from Firestore
        extra = "allow"


class RestaurantRecommendation(BaseModel):
    """Restaurant recommendation with score and reasoning"""
    restaurant: Restaurant
    score: float
    reasoning: str