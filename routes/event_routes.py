"""
Event Management Routes
"""
from flask import Blueprint, request, jsonify, current_app
from services.notification_service import NotificationService
import secrets
import logging

logger = logging.getLogger(__name__)
event_bp = Blueprint('events', __name__)

@event_bp.route('', methods=['POST'])
def create_event():
    """Create a new event"""
    try:
        data = request.get_json()
        
        # Check if this is a text-based event creation
        if 'description' in data and 'organizer_phone' in data:
            try:
                # Parse the text description
                from services.text_parser_service import parse_event_text
                logger.info(f"Attempting to parse text: {data['description']}")
                parsed_data = parse_event_text(data['description'])
                logger.info(f"Parsed data: {parsed_data}")
                
                # Convert parsed data to match API format
                data = {
                    'organizer_phone': data['organizer_phone'],
                    'location': parsed_data['location'],
                    'occasion_description': parsed_data['occasion_description'],
                    'expected_attendee_count': parsed_data.get('expected_attendee_count'),
                    'preferred_date': parsed_data['preferred_date'],
                    'preferred_time_slots': parsed_data.get('preferred_time_slots', []),
                    'dietary_restrictions': parsed_data.get('dietary_restrictions', []),
                    'cuisine_preferences': parsed_data.get('cuisine_preferences', []),
                    'budget_min': parsed_data.get('budget_min'),
                    'budget_max': parsed_data.get('budget_max'),
                    'extra_info': parsed_data.get('extra_info')
                }
                
                # Convert expected_attendee_count to integer if present
                if data['expected_attendee_count'] is not None:
                    try:
                        data['expected_attendee_count'] = int(data['expected_attendee_count'])
                    except (ValueError, TypeError):
                        logger.warning(f"Could not convert expected_attendee_count to integer: {data['expected_attendee_count']}")
                logger.info(f"Converted data: {data}")
            except Exception as e:
                logger.error(f"Error parsing text description: {str(e)}")
                return jsonify({'error': f'Failed to parse event description: {str(e)}'}), 400
        
        # Validate required fields
        required_fields = ['organizer_phone', 'location', 'occasion_description', 'preferred_date']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        firebase_service = current_app.get_firebase_service()
        
        # Generate unique invitation link using frontend URL
        share_token = secrets.token_urlsafe(32)
        from config import Config
        frontend_url = Config.FRONTEND_BASE_URL.rstrip('/')
        invitation_link = f"{frontend_url}/events/{share_token}/respond"
        
        # Create event
        event_data = {
            'organizer_phone': data['organizer_phone'],
            'organizer_email': data.get('organizer_email', ''),
            'location': data['location'],
            'occasion_description': data['occasion_description'],
            'expected_attendee_count': data.get('expected_attendee_count'),
            'preferred_date': data['preferred_date'],  # Should be timestamp
            'preferred_time_slots': data.get('preferred_time_slots', []),
            'dietary_restrictions': data.get('dietary_restrictions', []),
            'cuisine_preferences': data.get('cuisine_preferences', []),
            'budget_min': data.get('budget_min'),
            'budget_max': data.get('budget_max'),
            'extra_info': data.get('extra_info'),
            'invitation_link': invitation_link,
            'invitation_token': share_token
        }
        
        event = firebase_service.create_event(event_data)
        # If invitees were provided, send invitation messages
        invitees = data.get('invitees', [])
        invitations_summary = None
        if invitees:
            try:
                notification_service = NotificationService()
                invitations_summary = notification_service.send_event_invitations(event, invitees)
            except Exception as e:
                logger.error(f"Error sending invitations: {str(e)}")

        resp = {
            'message': 'Event created successfully',
            'event': event
        }
        if invitations_summary is not None:
            resp['invitations'] = invitations_summary

        return jsonify(resp), 201
        
    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['GET'])
def get_event(event_id):
    """Retrieve event details"""
    try:
        firebase_service = current_app.get_firebase_service()
        event = firebase_service.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get responses count
        responses = firebase_service.get_event_responses(event_id)
        confirmed_count = sum(1 for r in responses if r.get('attendance_confirmed'))
        
        event['response_count'] = len(responses)
        event['confirmed_attendee_count'] = confirmed_count
        
        return jsonify({'event': event}), 200
        
    except Exception as e:
        logger.error(f"Error getting event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['PATCH'])
def update_event(event_id):
    """Update event"""
    try:
        data = request.get_json()
        
        firebase_service = current_app.get_firebase_service()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Update event
        update_data = {}
        allowed_fields = ['location', 'occasion_description', 'expected_attendee_count', 
                         'preferred_date', 'preferred_time_slots', 'status']
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        updated_event = firebase_service.update_event(event_id, update_data)
        
        return jsonify({
            'message': 'Event updated successfully',
            'event': updated_event
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Cancel/delete event"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Update status to cancelled instead of deleting
        firebase_service.update_event(event_id, {'status': 'cancelled'})
        
        return jsonify({'message': 'Event cancelled successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>/responses', methods=['GET'])
def get_event_responses(event_id):
    """Get all responses for an event"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        responses = firebase_service.get_event_responses(event_id)
        
        return jsonify({
            'event_id': event_id,
            'responses': responses,
            'count': len(responses)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting event responses: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/token/<invitation_token>', methods=['GET'])
def get_event_by_token(invitation_token):
    """Get event by invitation token"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Find event by invitation token
        events = firebase_service.db.collection('events').where('invitation_token', '==', invitation_token).stream()
        event = None
        for doc in events:
            event = doc.to_dict()
            break
        
        if not event:
            return jsonify({'error': 'Invalid invitation link'}), 404
        
        return jsonify({'event': event}), 200
        
    except Exception as e:
        logger.error(f"Error getting event by token: {str(e)}")
        return jsonify({'error': str(e)}), 500

