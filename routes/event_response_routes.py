"""
Event Response Routes
"""
from flask import Blueprint, request, jsonify, current_app
from services.ai_agent import AIAgentService
import logging

logger = logging.getLogger(__name__)
response_bp = Blueprint('event_responses', __name__)

@response_bp.route('/<event_id>/responses', methods=['POST'])
def submit_response(event_id):
    """Submit invitee response"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'respondent_phone' not in data:
            return jsonify({'error': 'respondent_phone is required'}), 400
        
        firebase_service = current_app.get_firebase_service()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Check if user exists, if not, create with onboarding data
        respondent_phone = data['respondent_phone']
        user = firebase_service.get_user(respondent_phone)
        
        if not user:
            # New user - create with onboarding data
            if 'dietary_restrictions' not in data or 'alcohol_preference' not in data:
                return jsonify({'error': 'New users must provide dietary_restrictions and alcohol_preference'}), 400
            user_data = {
                'phone_number': respondent_phone,
                'dietary_restrictions': data.get('dietary_restrictions', []),
                'alcohol_preference': data.get('alcohol_preference', 'no-preference'),
                'push_notifications_enabled': data.get('push_notifications_enabled', True),
                'email_notifications_enabled': data.get('email_notifications_enabled', True)
            }
            firebase_service.create_or_update_user(respondent_phone, user_data)
        
        # Create or update response
        response_data = {
            'event_id': event_id,
            'respondent_phone': respondent_phone,
            'attendance_confirmed': True,
            'event_specific_dietary_notes': data.get('event_specific_dietary_notes')
        }
        
        response = firebase_service.create_event_response(response_data)

        # Check if we should update event status
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        expected_count = event.get('expected_attendee_count')

        logger.info(f"Event {event_id}: {len(confirmed_attendees)} confirmed out of {expected_count} expected")

        if expected_count and len(confirmed_attendees) >= expected_count:
            logger.info(f"Event {event_id}: All attendees confirmed! Auto-generating recommendations...")
            # Update status
            firebase_service.update_event(event_id, {'status': 'ready_for_booking'})

            # Automatically generate recommendations when threshold is met
            try:
                # Build attendee preferences similar to ai_agent routes
                attendee_preferences = []
                for attendee in confirmed_attendees:
                    user = firebase_service.get_user(attendee['respondent_phone'])
                    if user:
                        attendee_preferences.append({
                            'phone': attendee['respondent_phone'],
                            'dietary_restrictions': user.get('dietary_restrictions', []),
                            'alcohol_preference': user.get('alcohol_preference', 'no-preference'),
                            'event_specific_notes': attendee.get('event_specific_dietary_notes'),
                            'location_override': attendee.get('location_preference_override')
                        })

                # Include organizer preferences
                organizer = firebase_service.get_user(event['organizer_phone'])
                if organizer:
                    attendee_preferences.append({
                        'phone': event['organizer_phone'],
                        'dietary_restrictions': organizer.get('dietary_restrictions', []),
                        'alcohol_preference': organizer.get('alcohol_preference', 'no-preference')
                    })

                # Get dislikes
                dislikes = firebase_service.get_event_attendee_dislikes(event_id)

                # Generate recommendations via AI service
                ai_service = AIAgentService(firebase_service)
                recommendations = ai_service.generate_recommendations(
                    event=event,
                    attendee_preferences=attendee_preferences,
                    dislikes=dislikes
                )

                # Save recommendations to Firestore
                firebase_service.save_recommendations(event_id, recommendations)
                logger.info(f"Event {event_id}: Recommendations saved successfully!")

                # NEW: Automatically trigger outbound calls to top 3 restaurants
                try:
                    logger.info(f"Event {event_id}: Initiating outbound calls to top restaurants...")
                    from services.outbound_call_service import OutboundCallService

                    call_service = OutboundCallService()

                    # Get confirmed attendees for party size
                    party_size = len(confirmed_attendees) + 1  # +1 for organizer

                    # Safely extract and convert Firestore values
                    preferred_date = event.get('preferred_date')
                    preferred_time_slots = event.get('preferred_time_slots', [])

                    # Convert Firestore timestamp to string if needed
                    if hasattr(preferred_date, 'strftime'):
                        preferred_date = preferred_date.strftime('%Y-%m-%d')
                    elif isinstance(preferred_date, str):
                        preferred_date = preferred_date
                    else:
                        preferred_date = None

                    booking_details = {
                        'party_size': party_size,
                        'booking_date': preferred_date,
                        'booking_time': preferred_time_slots[0] if preferred_time_slots else None,
                    }

                    # Show recommendation details before calling
                    recs = recommendations.get('recommendations', [])
                    logger.info(f"\nEvent {event_id}: === Restaurant Selection Details ===")
                    for idx, rec in enumerate(recs, 1):
                        logger.info(f"\nRestaurant #{idx}: {rec.get('restaurant_name', 'Unknown')}")
                        logger.info(f"Match Score: {rec.get('score', 0):.2f}")
                        logger.info(f"Cuisine: {rec.get('cuisine_type', 'Not specified')}")
                        logger.info(f"Price Level: {rec.get('price_level', 'Not specified')}")
                        logger.info(f"Reasoning:\n{rec.get('reasoning', 'No reasoning provided')}")
                        logger.info("-" * 50)

                    # Call top 3 restaurants
                    call_results = call_service.call_top_restaurants(
                        recs,
                        event,
                        booking_details,
                        max_calls=1
                    )

                    # Save call records
                    for result in call_results:
                        call_record = {
                            'event_id': event_id,
                            'recommendation_id': firebase_service.get_recommendations(event_id).get('id'),
                            'restaurant_name': result.get('restaurant_name'),
                            'restaurant_phone': result.get('restaurant_phone'),
                            'rank': result.get('rank'),
                            'call_initiated': result.get('call_initiated', False),
                            'conversation_id': result.get('conversation_id'),
                            'call_sid': result.get('call_sid'),
                            'success': result.get('success', False),
                            'error': result.get('error'),
                            'is_mock': result.get('is_mock', False),
                            'timestamp': result.get('timestamp'),
                            'status': 'pending'
                        }
                        firebase_service.create_call_record(call_record)

                    logger.info(f"Event {event_id}: Called {len(call_results)} restaurants successfully!")

                    # Update event to indicate calls were made
                    firebase_service.update_event(event_id, {'calls_initiated': True})

                except Exception as call_error:
                    logger.error(f"Event {event_id}: Auto-calling failed: {str(call_error)}")
                    # Don't fail the whole request if calling fails

            except Exception as e:
                logger.error(f"Auto-generation of recommendations failed: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
        
        return jsonify({
            'message': 'Response submitted successfully',
            'response': response
        }), 201
        
    except Exception as e:
        logger.error(f"Error submitting response: {str(e)}")
        return jsonify({'error': str(e)}), 500

