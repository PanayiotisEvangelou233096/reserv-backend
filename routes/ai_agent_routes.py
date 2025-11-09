"""
AI Agent Routes - Restaurant Recommendations
"""
from flask import Blueprint, request, jsonify, current_app
from services.ai_agent import AIAgentService
import logging

logger = logging.getLogger(__name__)
ai_agent_bp = Blueprint('ai_agent', __name__)

@ai_agent_bp.route('/events/<event_id>/generate-recommendations', methods=['POST'])
def generate_recommendations(event_id):
    """Trigger AI restaurant selection"""
    try:
        firebase_service = current_app.get_firebase_service()
        ai_service = AIAgentService(firebase_service)
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get all confirmed attendees
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        if not confirmed_attendees:
            return jsonify({'error': 'No confirmed attendees found'}), 400
        
        # Get all attendee preferences
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
        
        # Get organizer preferences
        organizer = firebase_service.get_user(event['organizer_phone'])
        if organizer:
            attendee_preferences.append({
                'phone': event['organizer_phone'],
                'dietary_restrictions': organizer.get('dietary_restrictions', []),
                'alcohol_preference': organizer.get('alcohol_preference', 'no-preference')
            })
        
        # Get all dislikes for attendees
        dislikes = firebase_service.get_event_attendee_dislikes(event_id)
        
        # Generate recommendations using AI
        recommendations = ai_service.generate_recommendations(
            event=event,
            attendee_preferences=attendee_preferences,
            dislikes=dislikes
        )
        
        # Save recommendations
        saved_recommendations = firebase_service.save_recommendations(event_id, recommendations)
        
        # Update event status
        firebase_service.update_event(event_id, {'status': 'ready_for_booking'})
        
        return jsonify({
            'message': 'Recommendations generated successfully',
            'recommendations': saved_recommendations
        }), 201
        
    except Exception as e:
        logger.error(f"Error generating recommendations: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ai_agent_bp.route('/events/<event_id>/recommendations', methods=['GET'])
def get_recommendations(event_id):
    """Retrieve recommendations for an event"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        recommendations = firebase_service.get_recommendations(event_id)
        
        if not recommendations:
            return jsonify({'error': 'No recommendations found. Generate recommendations first.'}), 404
        
        return jsonify({
            'event_id': event_id,
            'recommendations': recommendations
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {str(e)}")
        return jsonify({'error': str(e)}), 500

