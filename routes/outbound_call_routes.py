"""
Outbound Call Routes - API endpoints for automated restaurant calls
"""
from flask import Blueprint, request, jsonify, current_app
from services.outbound_call_service import OutboundCallService
import logging

logger = logging.getLogger(__name__)
outbound_call_bp = Blueprint('outbound_calls', __name__)


@outbound_call_bp.route('/events/<event_id>/call-restaurants', methods=['POST'])
def call_restaurants_for_event(event_id):
    """
    Automatically call top restaurants for an event

    Request body (optional):
    {
        "max_calls": 3,  // Number of restaurants to call (default: 3)
        "booking_details": {
            "party_size": 4,
            "booking_date": "2025-11-15",
            "booking_time": "19:00",
            "special_requests": "Window seat preferred"
        }
    }
    """
    try:
        firebase_service = current_app.get_firebase_service()
        call_service = OutboundCallService()
        data = request.get_json() or {}

        # Get event
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404

        # Get recommendations
        recommendations_doc = firebase_service.get_recommendations(event_id)
        if not recommendations_doc:
            return jsonify({'error': 'No recommendations found. Generate recommendations first.'}), 404

        recommendations = recommendations_doc.get('recommendations', [])
        if not recommendations:
            return jsonify({'error': 'No restaurants in recommendations'}), 404

        # Get confirmed attendees for party size
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        party_size = len(confirmed_attendees) + 1  # +1 for organizer

        # Prepare booking details
        booking_details = data.get('booking_details', {})
        booking_details.setdefault('party_size', party_size)
        booking_details.setdefault('booking_date', event.get('preferred_date'))
        booking_details.setdefault('booking_time', event.get('preferred_time_slots', ['19:00'])[0])

        # Get max calls
        max_calls = data.get('max_calls', 3)

        # Make calls to top restaurants
        logger.info(f"Calling top {max_calls} restaurants for event {event_id}")
        call_results = call_service.call_top_restaurants(
            recommendations,
            event,
            booking_details,
            max_calls=max_calls
        )

        # Save call results to Firebase
        call_records = []
        for result in call_results:
            call_record = {
                'event_id': event_id,
                'recommendation_id': recommendations_doc.get('id'),
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
                'status': 'pending'  # Will be updated when we get conversation outcome
            }

            # Save to Firebase
            saved_call = firebase_service.create_call_record(call_record)
            call_records.append(saved_call)

        # Update event status
        firebase_service.update_event(event_id, {
            'status': 'calling_restaurants',
            'calls_initiated': True
        })

        return jsonify({
            'message': f'Initiated calls to {len(call_results)} restaurants',
            'calls': call_records,
            'event_id': event_id
        }), 201

    except Exception as e:
        logger.error(f"Error calling restaurants: {str(e)}")
        return jsonify({'error': str(e)}), 500


@outbound_call_bp.route('/events/<event_id>/call-specific-restaurant', methods=['POST'])
def call_specific_restaurant(event_id):
    """
    Call a specific restaurant by rank

    Request body:
    {
        "rank": 1,  // Required: which restaurant to call
        "booking_details": {
            "party_size": 4,
            "booking_date": "2025-11-15",
            "booking_time": "19:00"
        }
    }
    """
    try:
        firebase_service = current_app.get_firebase_service()
        call_service = OutboundCallService()
        data = request.get_json()

        if not data or 'rank' not in data:
            return jsonify({'error': 'rank is required'}), 400

        # Get event
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404

        # Get recommendations
        recommendations_doc = firebase_service.get_recommendations(event_id)
        if not recommendations_doc:
            return jsonify({'error': 'No recommendations found'}), 404

        # Find restaurant by rank
        recommendations = recommendations_doc.get('recommendations', [])
        rank = data['rank']

        restaurant = None
        for rec in recommendations:
            if rec.get('rank') == rank:
                restaurant = rec
                break

        if not restaurant:
            return jsonify({'error': f'No restaurant found at rank {rank}'}), 404

        # Prepare booking details
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        party_size = len(confirmed_attendees) + 1

        booking_details = data.get('booking_details', {})
        booking_details.setdefault('party_size', party_size)
        booking_details.setdefault('booking_date', event.get('preferred_date'))
        booking_details.setdefault('booking_time', event.get('preferred_time_slots', ['19:00'])[0])

        # Prepare call data
        call_data = call_service.prepare_call_data_from_booking(
            restaurant,
            event,
            booking_details
        )

        # Make the call
        result = call_service.make_reservation_call(call_data)
        result['rank'] = rank

        # Save call record
        call_record = {
            'event_id': event_id,
            'recommendation_id': recommendations_doc.get('id'),
            'restaurant_name': result.get('restaurant_name'),
            'restaurant_phone': result.get('restaurant_phone'),
            'rank': rank,
            'call_initiated': result.get('call_initiated', False),
            'conversation_id': result.get('conversation_id'),
            'call_sid': result.get('call_sid'),
            'success': result.get('success', False),
            'error': result.get('error'),
            'is_mock': result.get('is_mock', False),
            'timestamp': result.get('timestamp'),
            'status': 'pending'
        }

        saved_call = firebase_service.create_call_record(call_record)

        return jsonify({
            'message': 'Call initiated successfully',
            'call': saved_call
        }), 201

    except Exception as e:
        logger.error(f"Error calling restaurant: {str(e)}")
        return jsonify({'error': str(e)}), 500


@outbound_call_bp.route('/calls/<call_id>/outcome', methods=['GET'])
def get_call_outcome(call_id):
    """
    Get the outcome of a call
    """
    try:
        firebase_service = current_app.get_firebase_service()
        call_service = OutboundCallService()

        # Get call record
        call_record = firebase_service.get_call_record(call_id)
        if not call_record:
            return jsonify({'error': 'Call record not found'}), 404

        conversation_id = call_record.get('conversation_id')
        if not conversation_id:
            return jsonify({'error': 'No conversation ID found'}), 400

        # Get outcome from ElevenLabs
        outcome = call_service.get_conversation_outcome(conversation_id)

        # Update call record with outcome
        update_data = {
            'status': 'completed',
            'reservation_accepted': outcome.get('reservation_accepted', False),
            'confirmation_number': outcome.get('confirmation_number'),
            'outcome_notes': outcome.get('notes'),
            'transcript': outcome.get('transcript'),
            'duration_seconds': outcome.get('duration_seconds'),
            'outcome_retrieved_at': outcome.get('timestamp')
        }
        firebase_service.update_call_record(call_id, update_data)

        return jsonify({
            'call_id': call_id,
            'outcome': outcome
        }), 200

    except Exception as e:
        logger.error(f"Error getting call outcome: {str(e)}")
        return jsonify({'error': str(e)}), 500


@outbound_call_bp.route('/events/<event_id>/calls', methods=['GET'])
def get_event_calls(event_id):
    """
    Get all call records for an event
    """
    try:
        firebase_service = current_app.get_firebase_service()

        # Check event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404

        # Get all calls for this event
        calls = firebase_service.get_event_calls(event_id)

        return jsonify({
            'event_id': event_id,
            'calls': calls,
            'total_calls': len(calls)
        }), 200

    except Exception as e:
        logger.error(f"Error getting event calls: {str(e)}")
        return jsonify({'error': str(e)}), 500


@outbound_call_bp.route('/webhook/elevenlabs', methods=['POST'])
def elevenlabs_webhook():
    """
    Webhook endpoint for ElevenLabs call status updates
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data received'}), 400

        # Extract conversation data
        conversation_id = data.get('conversation_id')
        event_type = data.get('event_type')

        logger.info(f"Received ElevenLabs webhook: {event_type} for conversation {conversation_id}")

        # Handle different event types
        if event_type == 'conversation_initiation':
            # Return required dynamic variables
            conversation_data = data.get('conversation_initiation_client_data', {})
            if isinstance(conversation_data, dict) and 'dynamic_variables' in conversation_data:
                dynamic_vars = conversation_data.get('dynamic_variables', {})
            else:
                dynamic_vars = conversation_data

            return jsonify({
                'client': dynamic_vars.get('client', dynamic_vars.get('customer_name', '')),
                'date': dynamic_vars.get('date', dynamic_vars.get('reservation_date', '')),
                'time': dynamic_vars.get('time', dynamic_vars.get('reservation_time', '')),
                'diet': dynamic_vars.get('diet', ''),
                'status': 'success',
                'timestamp': data.get('timestamp', '')
            }), 200

        elif event_type == 'conversation_completed':
            # Update call record with completion status
            # You could trigger get_conversation_outcome here
            pass

        return jsonify({'status': 'received'}), 200

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500
