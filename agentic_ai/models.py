"""Data models for restaurant planning system"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ParsedInput(BaseModel):
    """Parsed input from combined text - all responses in one"""
    attendee_count: int = Field(description="Number of people attending")
    location_preference: str = Field(description="Location preference")
    time_preference: str = Field(description="Preferred time")
    date: str = Field(description="Preferred date")
    budget_min: Optional[float] = Field(default=None, description="Minimum budget per person")
    budget_max: Optional[float] = Field(default=None, description="Maximum budget per person")
    dietary_restrictions: str = Field(default="", description="Combined dietary restrictions")
    cuisine_preferences: List[str] = Field(default_factory=list, description="List of preferred cuisines")


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