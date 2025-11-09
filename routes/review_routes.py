"""
Post-Event Review Routes
"""
from flask import Blueprint, request, jsonify
from firebase_service import FirebaseService
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)
review_bp = Blueprint('reviews', __name__)

@review_bp.route('/events/<event_id>/request-reviews', methods=['POST'])
def request_reviews(event_id):
    """Trigger review notifications"""
    try:
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Check if booking exists
        booking = firebase_service.get_event_booking(event_id)
        if not booking:
            return jsonify({'error': 'No booking found for this event'}), 404
        
        # Check if event is completed
        if event.get('status') != 'completed':
            return jsonify({'error': 'Event must be completed before requesting reviews'}), 400
        
        # Update event to mark reviews as requested
        firebase_service.update_event(event_id, {
            'reviews_requested': True,
            'reviews_requested_at': firestore.SERVER_TIMESTAMP
        })
        
        # Send notifications to all attendees
        from services.notification_service import NotificationService
        notification_service = NotificationService()
        
        # Get all confirmed attendees
        confirmed_attendees = firebase_service.get_confirmed_attendees(event_id)
        organizer = firebase_service.get_user(event['organizer_phone'])
        
        # Send to all attendees
        all_attendees = confirmed_attendees + [{
            'respondent_phone': event['organizer_phone'],
            'respondent_email': organizer.get('email', '') if organizer else ''
        }]
        
        notifications_sent = 0
        for attendee in all_attendees:
            if notification_service.send_review_request(
                event_id,
                attendee.get('respondent_phone'),
                attendee.get('respondent_email'),
                booking
            ):
                notifications_sent += 1
        
        return jsonify({
            'message': 'Review notifications sent',
            'event_id': event_id,
            'notifications_sent': notifications_sent,
            'total_attendees': len(all_attendees)
        }), 200
        
    except Exception as e:
        logger.error(f"Error requesting reviews: {str(e)}")
        return jsonify({'error': str(e)}), 500

@review_bp.route('/events/<event_id>/reviews', methods=['POST'])
def submit_review(event_id):
    """Submit a post-event review"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if 'reviewer_phone' not in data:
            return jsonify({'error': 'reviewer_phone is required'}), 400
        if 'overall_rating' not in data:
            return jsonify({'error': 'overall_rating is required'}), 400
        
        # Validate overall_rating
        overall_rating = data['overall_rating']
        if not isinstance(overall_rating, (int, float)) or overall_rating < 1 or overall_rating > 5:
            return jsonify({'error': 'overall_rating must be between 1 and 5'}), 400
        
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get booking
        booking = firebase_service.get_event_booking(event_id)
        if not booking:
            return jsonify({'error': 'No booking found for this event'}), 404
        
        # Validate optional ratings
        optional_ratings = ['food_quality_rating', 'service_rating', 'atmosphere_rating', 'value_rating']
        for rating_field in optional_ratings:
            if rating_field in data:
                rating = data[rating_field]
                if rating is not None and (not isinstance(rating, (int, float)) or rating < 1 or rating > 5):
                    return jsonify({'error': f'{rating_field} must be between 1 and 5'}), 400
        
        # Validate would_recommend
        if 'would_recommend' in data and data['would_recommend'] not in ['yes', 'no', 'maybe', None]:
            return jsonify({'error': 'would_recommend must be "yes", "no", or "maybe"'}), 400
        
        # Validate written_remarks length
        if 'written_remarks' in data and len(data['written_remarks']) > 500:
            return jsonify({'error': 'written_remarks must be 500 characters or less'}), 400
        
        # Create review
        review_data = {
            'event_id': event_id,
            'booking_id': booking.get('id'),
            'reviewer_phone': data['reviewer_phone'],
            'restaurant_name': booking['restaurant_name'],
            'restaurant_address': booking['restaurant_address'],
            'overall_rating': overall_rating,
            'food_quality_rating': data.get('food_quality_rating'),
            'service_rating': data.get('service_rating'),
            'atmosphere_rating': data.get('atmosphere_rating'),
            'value_rating': data.get('value_rating'),
            'would_recommend': data.get('would_recommend'),
            'written_remarks': data.get('written_remarks'),
            'added_to_blacklist': data.get('added_to_blacklist', False)
        }
        
        review = firebase_service.create_review(review_data)
        
        # If user blacklisted the restaurant, add to dislikes
        if data.get('added_to_blacklist', False):
            dislike_data = {
                'user_phone': data['reviewer_phone'],
                'restaurant_name': booking['restaurant_name'],
                'restaurant_address': booking['restaurant_address'],
                'dislike_type': 'permanent',
                'reason': data.get('dislike_reason', 'other'),
                'notes': data.get('dislike_notes')
            }
            firebase_service.add_restaurant_dislike(dislike_data)
        
        # Update aggregate ratings
        firebase_service.update_aggregate_ratings(
            booking['restaurant_name'],
            booking['restaurant_address']
        )
        
        return jsonify({
            'message': 'Review submitted successfully',
            'review': review
        }), 201
        
    except Exception as e:
        logger.error(f"Error submitting review: {str(e)}")
        return jsonify({'error': str(e)}), 500

@review_bp.route('/events/<event_id>/reviews', methods=['GET'])
def get_event_reviews(event_id):
    """Get all reviews for an event"""
    try:
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        reviews = firebase_service.get_event_reviews(event_id)
        
        return jsonify({
            'event_id': event_id,
            'reviews': reviews,
            'count': len(reviews)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting event reviews: {str(e)}")
        return jsonify({'error': str(e)}), 500

@review_bp.route('/restaurants/<restaurant_name>/reviews', methods=['GET'])
def get_restaurant_reviews(restaurant_name):
    """Get all reviews for a restaurant"""
    try:
        restaurant_address = request.args.get('address')
        if not restaurant_address:
            return jsonify({'error': 'restaurant address is required as query parameter'}), 400
        
        firebase_service = FirebaseService()
        reviews = firebase_service.get_restaurant_reviews(restaurant_name, restaurant_address)
        
        return jsonify({
            'restaurant_name': restaurant_name,
            'restaurant_address': restaurant_address,
            'reviews': reviews,
            'count': len(reviews)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting restaurant reviews: {str(e)}")
        return jsonify({'error': str(e)}), 500

@review_bp.route('/restaurants/<restaurant_name>/aggregate-rating', methods=['GET'])
def get_aggregate_rating(restaurant_name):
    """Get aggregate ratings for a restaurant"""
    try:
        restaurant_address = request.args.get('address')
        if not restaurant_address:
            return jsonify({'error': 'restaurant address is required as query parameter'}), 400
        
        firebase_service = FirebaseService()
        aggregate = firebase_service.get_aggregate_rating(restaurant_name, restaurant_address)
        
        if not aggregate:
            return jsonify({
                'restaurant_name': restaurant_name,
                'restaurant_address': restaurant_address,
                'message': 'No reviews found for this restaurant'
            }), 404
        
        return jsonify({
            'restaurant_name': restaurant_name,
            'restaurant_address': restaurant_address,
            'aggregate_rating': aggregate
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting aggregate rating: {str(e)}")
        return jsonify({'error': str(e)}), 500
