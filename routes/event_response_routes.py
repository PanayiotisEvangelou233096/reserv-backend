"""
Event Response Routes
"""
from flask import Blueprint, request, jsonify
from firebase_service import FirebaseService
from services.ai_agent import AIAgentService
import logging

logger = logging.getLogger(__name__)
response_bp = Blueprint('event_responses', __name__)


@response_bp.route('/<event_id>/responses', methods=['POST'])
def submit_response(event_id):
    """Submit invitee response. Now accepts a minimal payload: respondent_phone and prompt (optional)."""
    try:
        data = request.get_json()

        # Validate required fields
        if 'respondent_phone' not in data:
            return jsonify({'error': 'respondent_phone is required'}), 400

        firebase_service = FirebaseService()

        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404

        respondent_phone = data['respondent_phone']
        user = firebase_service.get_user(respondent_phone)

        if not user:
            # Create a minimal user profile (onboarding can be done later)
            user_data = {
                'phone_number': respondent_phone,
                'email': data.get('email', ''),
                'push_notifications_enabled': data.get('push_notifications_enabled', True),
                'email_notifications_enabled': data.get('email_notifications_enabled', True)
            }
            firebase_service.create_or_update_user(respondent_phone, user_data)

        # Create or update response (store respondent_prompt for later aggregation)
        response_data = {
            'event_id': event_id,
            'respondent_phone': respondent_phone,
            'respondent_email': data.get('email', user.get('email', '') if user else ''),
            'attendance_confirmed': data.get('attendance_confirmed', False),
            'location_preference_override': data.get('location_preference_override'),
            'event_specific_dietary_notes': data.get('event_specific_dietary_notes'),
            'respondent_prompt': data.get('prompt')
        }

        response = firebase_service.create_event_response(response_data)

        # Check if we should update event status
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        expected_count = event.get('expected_attendee_count')

        if expected_count and len(confirmed_attendees) >= expected_count:
            # Update status
            firebase_service.update_event(event_id, {'status': 'ready_for_booking'})

            # Automatically generate recommendations when threshold is met
            try:
                # Build concatenated prompts: organizer prompt + all respondents prompts
                prompts = []
                if event.get('organizer_prompt'):
                    prompts.append(event.get('organizer_prompt'))

                all_responses = firebase_service.get_event_responses(event_id)
                for resp in all_responses:
                    if resp.get('respondent_prompt'):
                        prompts.append(resp.get('respondent_prompt'))

                concatenated = "\n---\n".join(prompts)

                # Get dislikes
                dislikes = firebase_service.get_event_attendee_dislikes(event_id)

                ai_service = AIAgentService()
                # Prefer an LLM-driven recommendation method using concatenated prompts
                try:
                    recommendations = ai_service.generate_recommendations_from_prompts(event, concatenated, dislikes)
                except AttributeError:
                    # Fallback to existing generation using structured preferences
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
                    recommendations = ai_service.generate_recommendations(
                        event=event,
                        attendee_preferences=attendee_preferences,
                        dislikes=dislikes
                    )

                # Save recommendations to Firestore
                firebase_service.save_recommendations(event_id, recommendations)

            except Exception as e:
                logger.error(f"Auto-generation of recommendations failed: {str(e)}")

        return jsonify({
            'message': 'Response submitted successfully',
            'response': response
        }), 201

    except Exception as e:
        logger.error(f"Error submitting response: {str(e)}")
        return jsonify({'error': str(e)}), 500

