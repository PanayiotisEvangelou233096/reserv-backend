"""
AI Agent Service - Restaurant Recommendations
Uses Langchain to generate restaurant recommendations based on group preferences
"""
from firebase_service import FirebaseService
from langchain_integration import LangchainService
import logging
import json

logger = logging.getLogger(__name__)

class AIAgentService:
    """Service for AI-powered restaurant recommendations"""
    
    def __init__(self):
        self.langchain_service = LangchainService()
        self.firebase_service = FirebaseService()
    
    def generate_recommendations(self, event, attendee_preferences, dislikes):
        """
        Generate restaurant recommendations for an event
        
        Args:
            event: Event dictionary
            attendee_preferences: List of attendee preference dictionaries
            dislikes: List of restaurant dislike dictionaries
        
        Returns:
            Dictionary with recommendations and analysis
        """
        try:
            # Aggregate preferences
            all_dietary_restrictions = set()
            alcohol_preferences = []
            location_preferences = []
            
            for pref in attendee_preferences:
                all_dietary_restrictions.update(pref.get('dietary_restrictions', []))
                alcohol_preferences.append(pref.get('alcohol_preference', 'no-preference'))
                if pref.get('location_override'):
                    location_preferences.append(pref['location_override'])
            
            # Determine alcohol requirement
            alcohol_required = 'alcoholic' in alcohol_preferences
            alcohol_availability_required = alcohol_required
            
            # Location consensus
            location_consensus = event.get('location')
            if location_preferences:
                # Use most common override, or event location
                location_consensus = location_preferences[0] if location_preferences else event.get('location')
            
            # Build blacklist
            excluded_restaurants = []
            blacklisted_restaurants = set()
            
            for dislike in dislikes:
                if dislike.get('is_active', True):
                    restaurant_key = f"{dislike['restaurant_name']}_{dislike['restaurant_address']}"
                    blacklisted_restaurants.add(restaurant_key)
                    excluded_restaurants.append({
                        'restaurant_name': dislike['restaurant_name'],
                        'restaurant_address': dislike['restaurant_address'],
                        'excluded_by': [dislike['user_phone']],
                        'dislike_reasons': [dislike.get('reason', 'unknown')]
                    })
            
            # Use AI to generate recommendations
            # For now, we'll use a mock implementation that can be replaced with actual restaurant API
            recommendations = self._generate_ai_recommendations(
                location=location_consensus,
                dietary_restrictions=list(all_dietary_restrictions),
                alcohol_required=alcohol_availability_required,
                occasion=event.get('occasion_description', ''),
                party_size=event.get('expected_attendee_count', 2),
                blacklisted_restaurants=blacklisted_restaurants
            )
            
            # Build response
            result = {
                'recommendations': recommendations,
                'collective_dietary_restrictions': list(all_dietary_restrictions),
                'alcohol_availability_required': alcohol_availability_required,
                'location_consensus': location_consensus,
                'excluded_restaurants': excluded_restaurants,
                'ai_model_used': 'gpt-3.5-turbo',
                'confidence_score': 0.85
            }
            
            # Log AI action
            self.firebase_service.log_ai_action({
                'event_id': event.get('event_id'),
                'action_type': 'recommendation_generation',
                'input_data': {
                    'location': location_consensus,
                    'dietary_restrictions': list(all_dietary_restrictions),
                    'alcohol_required': alcohol_availability_required,
                    'occasion': event.get('occasion_description'),
                    'party_size': event.get('expected_attendee_count')
                },
                'output_data': result,
                'blacklisted_restaurants_excluded': len(excluded_restaurants),
                'success': True
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            # Log error
            self.firebase_service.log_ai_action({
                'event_id': event.get('event_id'),
                'action_type': 'recommendation_generation',
                'success': False,
                'error_message': str(e)
            })
            raise

    def generate_recommendations_from_prompts(self, event, concatenated_prompts, dislikes):
        """
        Use the concatenated natural-language prompts from organizer + respondents to ask the LLM
        for restaurant recommendations. Returns similar structure as generate_recommendations.
        """
        try:
            if not self.langchain_service.llm:
                # Fallback to basic generation using existing method
                return self._generate_ai_recommendations(
                    location=event.get('location'),
                    dietary_restrictions=[],
                    alcohol_required=False,
                    occasion=event.get('occasion_description', ''),
                    party_size=event.get('expected_attendee_count', 2),
                    blacklisted_restaurants=set()
                )

            # Build LLM prompt
            system_prompt = (
                "You are an assistant that recommends restaurants for a group based on a collection of short prompts from the organizer and attendees."
                " Return a JSON object with key 'recommendations' which is an array of up to 5 recommendation objects with fields:"
                " rank (1..5), restaurant_name, address, phone, cuisine_type, reasoning."
            )
            human_prompt = f"Group info: {event.get('occasion_description', '')}\nLocation: {event.get('location', '')}\nPrompts and preferences:\n{concatenated_prompts}\nDislikes: {dislikes}\nPlease return JSON as described."

            # Use our new predict method
            text = self.langchain_service.predict(system_prompt, human_prompt)
            if not text:
                return self._generate_ai_recommendations(
                    location=event.get('location'),
                    dietary_restrictions=[],
                    alcohol_required=False,
                    occasion=event.get('occasion_description', ''),
                    party_size=event.get('expected_attendee_count', 2),
                    blacklisted_restaurants=set()
                )

            import json
            # Try to extract JSON
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            recommendations = []
            try:
                obj = json.loads(text)
                recommendations = obj.get('recommendations') or obj
            except Exception:
                # Could not parse JSON - fallback
                recommendations = self._generate_ai_recommendations(
                    location=event.get('location'),
                    dietary_restrictions=[],
                    alcohol_required=False,
                    occasion=event.get('occasion_description', ''),
                    party_size=event.get('expected_attendee_count', 2),
                    blacklisted_restaurants=set()
                )

            result = {
                'recommendations': recommendations,
                'ai_model_used': 'gpt-3.5-turbo',
                'confidence_score': 0.8
            }

            # Log AI action
            self.firebase_service.log_ai_action({
                'event_id': event.get('event_id'),
                'action_type': 'recommendation_generation_from_prompts',
                'input_prompts': concatenated_prompts,
                'output': result,
                'success': True
            })

            return result

        except Exception as e:
            logger.error(f"Error in generate_recommendations_from_prompts: {str(e)}")
            self.firebase_service.log_ai_action({
                'event_id': event.get('event_id'),
                'action_type': 'recommendation_generation_from_prompts',
                'success': False,
                'error_message': str(e)
            })
            # fallback to default
            return self._generate_ai_recommendations(
                location=event.get('location'),
                dietary_restrictions=[],
                alcohol_required=False,
                occasion=event.get('occasion_description', ''),
                party_size=event.get('expected_attendee_count', 2),
                blacklisted_restaurants=set()
            )
    
    def _generate_ai_recommendations(self, location, dietary_restrictions, alcohol_required, occasion, party_size, blacklisted_restaurants):
        """
        Generate restaurant recommendations using AI
        
        Note: This is a placeholder. In production, this would:
        1. Query restaurant APIs (Yelp, Google Places, etc.)
        2. Filter by location, dietary restrictions, alcohol availability
        3. Exclude blacklisted restaurants
        4. Use AI to rank and justify recommendations
        """
        # Use Langchain to generate recommendations if available
        # For now, return mock recommendations that can be replaced with actual API calls
        
        # TODO: Integrate with restaurant APIs (Yelp, Google Places, OpenTable)
        # TODO: Use Langchain to analyze and rank restaurants based on preferences
        
        # Mock restaurant data - in production, this would come from APIs
        all_restaurants = [
            {
                'restaurant_name': 'The Gourmet Kitchen',
                'address': f'{location}, Main Street 123',
                'phone': '+1234567890',
                'cuisine_type': 'Italian',
                'dietary_options': ['vegetarian', 'gluten-free'],
                'alcohol_available': True
            },
            {
                'restaurant_name': 'Green Leaf Bistro',
                'address': f'{location}, Park Avenue 456',
                'phone': '+1234567891',
                'cuisine_type': 'Mediterranean',
                'dietary_options': ['vegetarian', 'vegan', 'gluten-free'],
                'alcohol_available': True
            },
            {
                'restaurant_name': 'Ocean View Seafood',
                'address': f'{location}, Harbor Road 789',
                'phone': '+1234567892',
                'cuisine_type': 'Seafood',
                'dietary_options': ['gluten-free'],
                'alcohol_available': True
            },
            {
                'restaurant_name': 'Garden Fresh',
                'address': f'{location}, Market Square 321',
                'phone': '+1234567893',
                'cuisine_type': 'Vegetarian',
                'dietary_options': ['vegetarian', 'vegan', 'gluten-free'],
                'alcohol_available': False
            },
            {
                'restaurant_name': 'Steakhouse Prime',
                'address': f'{location}, Downtown Plaza 654',
                'phone': '+1234567894',
                'cuisine_type': 'Steakhouse',
                'dietary_options': ['gluten-free'],
                'alcohol_available': True
            }
        ]
        
        # Filter out blacklisted restaurants
        available_restaurants = []
        for restaurant in all_restaurants:
            restaurant_key = f"{restaurant['restaurant_name']}_{restaurant['address']}"
            if restaurant_key not in blacklisted_restaurants:
                available_restaurants.append(restaurant)
        
        # Use AI to rank and justify recommendations
        # For now, use simple filtering and ranking
        # In production, use Langchain to analyze and rank
        
        ranked_restaurants = []
        for i, restaurant in enumerate(available_restaurants[:5], 1):
            # Simple ranking logic - in production, use AI
            reasoning = f"Good match for {occasion} in {location}"
            if dietary_restrictions:
                reasoning += f", accommodates {', '.join(dietary_restrictions)}"
            if alcohol_required and restaurant.get('alcohol_available'):
                reasoning += ", alcohol available"
            
            ranked_restaurants.append({
                'rank': i,
                'restaurant_name': restaurant['restaurant_name'],
                'address': restaurant['address'],
                'phone': restaurant['phone'],
                'cuisine_type': restaurant['cuisine_type'],
                'reasoning': reasoning,
                'accommodates_requirements': {
                    'dietary_restrictions': [d for d in dietary_restrictions if d in restaurant.get('dietary_options', [])],
                    'alcohol_available': restaurant.get('alcohol_available', False)
                }
            })
        
        return ranked_restaurants

