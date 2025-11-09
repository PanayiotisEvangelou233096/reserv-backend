"""
AI Agent Service - Restaurant Recommendations
Uses agentic-ai workflow to generate restaurant recommendations based on group preferences
"""
from agentic_ai.restaurant_planner import app as restaurant_planner
import logging
import json
from .restaurant_planner import app as restaurant_planner

logger = logging.getLogger(__name__)

class AIAgentService:
    """Service for AI-powered restaurant recommendations"""
    
    def __init__(self, firebase_service):
        self.firebase_service = firebase_service
    
    def generate_recommendations(self, event, attendee_preferences, dislikes):
        """
        Generate restaurant recommendations for an event using agentic-ai workflow and Firestore restaurant data
        """
        try:
            # Build combined input from all preferences
            combined_prompts = []
            
            # Add event details
            event_prompt = f"Event Details: Location: {event.get('location', 'Amsterdam')}, "
            event_prompt += f"Type: {event.get('occasion_description', 'Not specified')}, "
            event_prompt += f"Date: {event.get('preferred_date', 'Not specified')}, "
            event_prompt += f"Time: {event.get('preferred_time_slots', ['Not specified'])[0]}, "
            event_prompt += f"Number of attendees: {len(attendee_preferences)}"
            
            # Add budget information
            if event.get('budget_min') and event.get('budget_max'):
                event_prompt += f", Budget: €{event.get('budget_min')}-€{event.get('budget_max')} per person"
            elif event.get('budget_max'):
                event_prompt += f", Budget: Up to €{event.get('budget_max')} per person"
            elif event.get('budget_min'):
                event_prompt += f", Budget: From €{event.get('budget_min')} per person"

            # Add cuisine preferences
            if event.get('cuisine_preferences'):
                event_prompt += f", Preferred cuisines: {', '.join(event.get('cuisine_preferences'))}"

            # Add extra information
            if event.get('extra_info'):
                event_prompt += f"\nAdditional requirements: {event.get('extra_info')}"
                
            combined_prompts.append(event_prompt)
            
            # Add each attendee's preferences
            for i, pref in enumerate(attendee_preferences, 1):
                prompt = f"Attendee {i}: "
                if pref.get('dietary_restrictions'):
                    prompt += f"Dietary restrictions: {', '.join(pref['dietary_restrictions'])}. "
                if pref.get('cuisine_preferences'):
                    prompt += f"Preferred cuisines: {', '.join(pref['cuisine_preferences'])}. "
                if pref.get('budget'):
                    prompt += f"Budget: {pref['budget']}. "
                if pref.get('event_specific_notes'):
                    prompt += f"Notes: {pref['event_specific_notes']}."
                combined_prompts.append(prompt)

            combined_input = '\n'.join(combined_prompts)
            print(f"COMBINED INPUT: {combined_input}")
            # Initialize workflow state
            initial_state = {
                "input": combined_input,
                "attendee_count": len(attendee_preferences),
                "location_preference": event.get('location', 'Amsterdam'),
                "time_preference": event.get('time', 'Evening'),
                "date": event.get('date', 'Not specified'),
                "budget_min": None,  # Will be parsed from input
                "budget_max": None,  # Will be parsed from input
                "dietary_restrictions": None,  # Will be parsed from input
                "cuisine_preferences": [],  # Will be parsed from input
                "restaurant_candidates": [],
                "top_recommendations": [],
                "current_attempt": 0,
                "messages": [],
                "dislikes": dislikes  # Pass blacklisted restaurants to workflow
            }
            
            # Run the workflow (blacklisted restaurants are already filtered before scoring)
            result = restaurant_planner.invoke(initial_state)
            
            # Post-filtering safety net (should rarely catch anything since filtering happens before scoring)
            # Build a set of blacklisted location_ids and restaurant name+address combinations
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
            
            # Format the response and filter blacklisted restaurants (safety net)
            recommendations = []
            logger.info("=== AI Recommendation Process ===")
            logger.info(f"Input Requirements:\n{combined_input}")
            logger.info(f"Number of recommendations found: {len(result.get('top_recommendations', []))}")
            logger.info(f"Blacklisted location_ids: {blacklisted_location_ids}")
            logger.info(f"Blacklisted restaurants (name, address): {len(blacklisted_restaurants)}")
            logger.info("Note: Blacklisted restaurants are filtered BEFORE scoring for efficiency")
            
            rank = 1
            for rec in result.get('top_recommendations', []):
                # Get restaurant location_id
                restaurant_location_id = getattr(rec.restaurant, 'location_id', None)
                
                # Get restaurant name and address for matching
                restaurant_name = rec.restaurant.name
                restaurant_address_obj = getattr(rec.restaurant, 'address_obj', {})
                if isinstance(restaurant_address_obj, dict):
                    address_parts = [
                        restaurant_address_obj.get('street', ''),
                        restaurant_address_obj.get('city', ''),
                        restaurant_address_obj.get('state', ''),
                        restaurant_address_obj.get('country', '')
                    ]
                    restaurant_address = ', '.join(filter(None, address_parts))
                else:
                    restaurant_address = str(restaurant_address_obj) if restaurant_address_obj else ''
                
                # Check if restaurant is blacklisted
                is_blacklisted = False
                if restaurant_location_id and restaurant_location_id in blacklisted_location_ids:
                    is_blacklisted = True
                    logger.info(f"Filtered out {restaurant_name} (location_id: {restaurant_location_id})")
                elif (restaurant_name.lower().strip(), restaurant_address.lower().strip()) in blacklisted_restaurants:
                    is_blacklisted = True
                    logger.info(f"Filtered out {restaurant_name} (name+address match)")
                
                if is_blacklisted:
                    continue  # Skip blacklisted restaurants
                
                restaurant_data = {
                    'rank': rank,
                    'restaurant_name': restaurant_name,
                    'address': restaurant_address_obj,
                    'phone': getattr(rec.restaurant, 'phone', ''),
                    'rating': getattr(rec.restaurant, 'rating', 0.0),
                    'cuisine': getattr(rec.restaurant, 'cuisine', []),
                    'cuisine_type': ', '.join(getattr(rec.restaurant, 'cuisine', [])),
                    'price_level': getattr(rec.restaurant, 'price_level', 'N/A'),
                    'location_id': restaurant_location_id,
                    'score': rec.score,
                    'reasoning': rec.reasoning
                }
                recommendations.append(restaurant_data)
                
                # Log detailed reasoning for each recommendation
                logger.info(f"\nRecommendation #{rank}: {restaurant_name}")
                logger.info(f"Match Score: {rec.score:.2f}")
                logger.info(f"Cuisine: {restaurant_data['cuisine_type']}")
                logger.info(f"Price Level: {restaurant_data['price_level']}")
                logger.info(f"Rating: {restaurant_data['rating']}")
                logger.info(f"Reasoning:\n{rec.reasoning}")
                
                rank += 1
            
            # Log overall decision process
            logger.info("\n=== Selection Summary ===")
            logger.info(f"Total restaurants considered: {len(result.get('restaurant_candidates', []))}")
            logger.info(f"Final recommendations after filtering: {len(recommendations)}")
            logger.info(f"Messages from selection process:")
            for msg in result.get('messages', []):
                logger.info(f"- {msg}")
            
            return {
                'recommendations': recommendations,
                'messages': result.get('messages', [])
            }
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {str(e)}")
            return {'error': str(e)}
    

