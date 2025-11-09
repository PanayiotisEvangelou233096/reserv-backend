"""
Booking Routes
"""
from flask import Blueprint, request, jsonify, Response, current_app
from services.booking_service import BookingService
from services.calendar_service import CalendarService
from config import Config
import logging

logger = logging.getLogger(__name__)
booking_bp = Blueprint('bookings', __name__)

@booking_bp.route('/events/<event_id>/book', methods=['POST'])
def book_restaurant(event_id):
    """Execute restaurant booking"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'recommendation_rank' not in data:
            return jsonify({'error': 'recommendation_rank is required'}), 400
        
        firebase_service = current_app.get_firebase_service()
        booking_service = BookingService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get recommendations
        recommendations_doc = firebase_service.get_recommendations(event_id)
        if not recommendations_doc:
            return jsonify({'error': 'No recommendations found. Generate recommendations first.'}), 404
        
        recommendations = recommendations_doc.get('recommendations', [])
        rank = data['recommendation_rank']
        
        # Find the restaurant at the specified rank
        selected_restaurant = None
        for rec in recommendations:
            if rec.get('rank') == rank:
                selected_restaurant = rec
                break
        
        if not selected_restaurant:
            return jsonify({'error': f'No restaurant found at rank {rank}'}), 404
        
        # Get confirmed attendees count
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        party_size = len(confirmed_attendees) + 1  # +1 for organizer
        
        # Attempt booking
        booking_result = booking_service.attempt_booking(
            restaurant=selected_restaurant,
            event=event,
            party_size=party_size
        )
        
        if not booking_result['success']:
            return jsonify({
                'error': 'Booking failed',
                'message': booking_result.get('message', 'Restaurant unavailable'),
                'restaurant': selected_restaurant
            }), 400
        
        # Format address if it's an object
        restaurant_address = selected_restaurant.get('address', '')
        if isinstance(restaurant_address, dict):
            # Convert address object to string
            parts = []
            if restaurant_address.get('street'):
                parts.append(restaurant_address['street'])
            if restaurant_address.get('city'):
                parts.append(restaurant_address['city'])
            if restaurant_address.get('state'):
                parts.append(restaurant_address['state'])
            if restaurant_address.get('country'):
                parts.append(restaurant_address['country'])
            restaurant_address = ', '.join(parts) if parts else 'Address not available'

        # Get the phone number (use debug phone if enabled)
        restaurant_phone = selected_restaurant.get('phone', '')
        if Config.USE_DEBUG_PHONE:
            restaurant_phone = Config.DEBUG_PHONE_NUMBER
            logger.info(f"Using debug phone number: {restaurant_phone}")

        # Create booking record
        booking_data = {
            'event_id': event_id,
            'recommendation_id': recommendations_doc.get('id'),
            'restaurant_name': selected_restaurant['restaurant_name'],
            'restaurant_address': restaurant_address,
            'restaurant_phone': restaurant_phone,
            'restaurant_cuisine_type': selected_restaurant.get('cuisine_type', ''),
            'booking_date': event['preferred_date'],
            'booking_time': data.get('booking_time', event.get('preferred_time_slots', [None])[0]),
            'party_size': party_size,
            'booking_confirmation_number': booking_result.get('confirmation_number')
        }
        
        booking = firebase_service.create_booking(booking_data)
        
        # Send calendar invites and notifications
        from services.calendar_service import CalendarService
        from services.notification_service import NotificationService
        calendar_service = CalendarService()
        notification_service = NotificationService()
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        organizer = firebase_service.get_user(event['organizer_phone'])

        # Build attendees list (ensure organizer included)
        all_attendees = []
        for a in confirmed_attendees:
            all_attendees.append({
                'respondent_phone': a.get('respondent_phone'),
                'respondent_email': a.get('respondent_email', '')
            })

        # Add organizer
        all_attendees.append({
            'respondent_phone': event['organizer_phone'],
            'respondent_email': organizer.get('email', '') if organizer else ''
        })

        # Try to send calendar invites (mocked) and generate calendar links/ics
        try:
            calendar_result = calendar_service.send_calendar_invites(booking, all_attendees)

            # Generate a single Google Calendar link for the booking (can be shared)
            google_link = calendar_service.generate_google_calendar_link(booking)
            ical_content = None
            try:
                ical_content = calendar_service.generate_ical_file(booking)
            except Exception:
                ical_content = None

            # Send booking confirmation notifications (mock)
            attendee_phones = [a.get('respondent_phone') for a in all_attendees if a.get('respondent_phone')]
            attendee_emails = [a.get('respondent_email') for a in all_attendees if a.get('respondent_email')]
            notification_service.send_booking_confirmation(event_id, attendee_phones, attendee_emails, booking)

            # Update booking record with calendar info
            update_data = {
                'calendar_invites_sent': calendar_result.get('success', False),
                'calendar_event_ids': calendar_result.get('calendar_event_ids', []),
                'google_calendar_link': google_link
            }
            firebase_service.update_booking(booking['id'], update_data)

        except Exception as e:
            logger.error(f"Error handling calendar invites/notifications: {str(e)}")
        
        # Update event status and store booking ID
        firebase_service.update_event(event_id, {
            'status': 'booked',
            'booking_id': booking['id']
        })
        
        return jsonify({
            'message': 'Restaurant booked successfully',
            'booking': booking,
            'calendar_invites_sent': calendar_result.get('success', False)
        }), 201
        
    except Exception as e:
        logger.error(f"Error booking restaurant: {str(e)}")
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/bookings/<booking_id>', methods=['GET'])
def get_booking(booking_id):
    """Retrieve booking details"""
    try:
        firebase_service = current_app.get_firebase_service()
        booking = firebase_service.get_booking(booking_id)
        
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        return jsonify({'booking': booking}), 200
        
    except Exception as e:
        logger.error(f"Error getting booking: {str(e)}")
        return jsonify({'error': str(e)}), 500


@booking_bp.route('/events/<event_id>/booking', methods=['GET'])
def get_event_booking(event_id):
    """Retrieve the latest booking for an event"""
    try:
        firebase_service = current_app.get_firebase_service()
        booking = firebase_service.get_event_booking(event_id)

        # Return booking or null if none
        return jsonify({'booking': booking}), 200

    except Exception as e:
        logger.error(f"Error getting event booking: {str(e)}")
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/bookings/<booking_id>/calendar.ics', methods=['GET'])
def get_booking_ical(booking_id):
    """Get iCal file for booking"""
    try:
        firebase_service = current_app.get_firebase_service()
        calendar_service = CalendarService()
        
        # Get booking details
        booking = firebase_service.get_booking(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
            
        # Generate iCal content
        ical_content = calendar_service.generate_ical_file(booking)
        
        # Return as downloadable file
        from flask import Response
        response = Response(ical_content)
        response.headers['Content-Type'] = 'text/calendar'
        response.headers['Content-Disposition'] = f'attachment; filename=booking_{booking_id}.ics'
        return response
        
    except Exception as e:
        logger.error(f"Error generating iCal file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/bookings/<booking_id>/complete', methods=['PATCH'])
def complete_booking(booking_id):
    """Mark booking as completed"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if booking exists
        booking = firebase_service.get_booking(booking_id)
        if not booking:
            return jsonify({'error': 'Booking not found'}), 404
        
        # Mark as completed
        completed_booking = firebase_service.complete_booking(booking_id)
        
        # Update event status
        if booking.get('event_id'):
            firebase_service.update_event(booking['event_id'], {'status': 'completed'})
        
        return jsonify({
            'message': 'Booking marked as completed',
            'booking': completed_booking
        }), 200
        
    except Exception as e:
        logger.error(f"Error completing booking: {str(e)}")
        return jsonify({'error': str(e)}), 500

