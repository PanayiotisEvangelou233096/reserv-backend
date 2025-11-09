import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
import logging

logger = logging.getLogger(__name__)

class FirebaseService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FirebaseService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Try to get credentials from environment variable first (for Railway/production)
            creds_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
            
            if creds_json:
                logger.info("Loading Firebase credentials from environment variable")
                cred = credentials.Certificate(json.loads(creds_json))
            else:
                # Fallback to file (for local development)
                creds_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
                logger.info(f"Loading Firebase credentials from file: {creds_path}")
                cred = credentials.Certificate(creds_path)
            
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            logger.info("Firebase initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    # ==================== USER MANAGEMENT ====================
    
    def create_or_update_user(self, phone_number, user_data):
        """Create or update user profile"""
        doc_ref = self.db.collection('users').document(phone_number)
        user_data['phone_number'] = phone_number
        user_data['updated_at'] = firestore.SERVER_TIMESTAMP
        if not doc_ref.get().exists:
            user_data['created_at'] = firestore.SERVER_TIMESTAMP
        
        doc_ref.set(user_data, merge=True)
        return doc_ref.get().to_dict()
    
    def get_user(self, phone_number):
        """Get user by phone number"""
        doc = self.db.collection('users').document(phone_number).get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def update_user_preferences(self, phone_number, preferences):
        """Update user preferences"""
        doc_ref = self.db.collection('users').document(phone_number)
        update_data = {
            **preferences,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        doc_ref.update(update_data)
        return doc_ref.get().to_dict()
    
    # ==================== EVENT MANAGEMENT ====================
    
    def create_event(self, event_data):
        """Create a new event"""
        doc_ref = self.db.collection('events').document()
        event_data['event_id'] = doc_ref.id
        event_data['status'] = 'created'
        event_data['reviews_requested'] = False
        event_data['reviews_requested_at'] = None
        event_data['created_at'] = firestore.SERVER_TIMESTAMP
        event_data['updated_at'] = firestore.SERVER_TIMESTAMP
        
        doc_ref.set(event_data)
        return doc_ref.get().to_dict()
    
    def get_event(self, event_id):
        """Get event by ID"""
        doc = self.db.collection('events').document(event_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def update_event(self, event_id, update_data):
        """Update event"""
        doc_ref = self.db.collection('events').document(event_id)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.update(update_data)
        return doc_ref.get().to_dict()
    
    def delete_event(self, event_id):
        """Delete event"""
        self.db.collection('events').document(event_id).delete()
    
    def get_event_responses(self, event_id):
        """Get all responses for an event"""
        responses = []
        docs = self.db.collection('event_responses').where('event_id', '==', event_id).stream()
        for doc in docs:
            responses.append(doc.to_dict())
        return responses
    
    def get_confirmed_attendees(self, event_id):
        """Get all confirmed attendees for an event"""
        responses = []
        docs = self.db.collection('event_responses').where('event_id', '==', event_id).where('attendance_confirmed', '==', True).stream()
        for doc in docs:
            responses.append(doc.to_dict())
        return responses
    
    # ==================== EVENT RESPONSES ====================
    
    def create_event_response(self, response_data):
        """Create or update event response"""
        # Check if response already exists
        existing = self.db.collection('event_responses').where('event_id', '==', response_data['event_id']).where('respondent_phone', '==', response_data['respondent_phone']).stream()
        existing_doc = None
        for doc in existing:
            existing_doc = doc
            break
        
        if existing_doc:
            # Update existing response
            doc_ref = self.db.collection('event_responses').document(existing_doc.id)
            response_data['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(response_data)
            return doc_ref.get().to_dict()
        else:
            # Create new response
            doc_ref = self.db.collection('event_responses').document()
            response_data['responded_at'] = firestore.SERVER_TIMESTAMP
            response_data['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.set(response_data)
            return doc_ref.get().to_dict()
    
    # ==================== RESTAURANT DISLIKES ====================
    
    def add_restaurant_dislike(self, dislike_data):
        """Add restaurant to user's blacklist"""
        doc_ref = self.db.collection('restaurant_dislikes').document()
        dislike_data['is_active'] = True
        dislike_data['created_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(dislike_data)
        return doc_ref.get().to_dict()
    
    def get_user_dislikes(self, user_phone):
        """Get all active dislikes for a user"""
        dislikes = []
        docs = self.db.collection('restaurant_dislikes').where('user_phone', '==', user_phone).where('is_active', '==', True).stream()
        for doc in docs:
            dislike = doc.to_dict()
            dislike['id'] = doc.id
            dislikes.append(dislike)
        return dislikes
    
    def get_event_attendee_dislikes(self, event_id):
        """Get all dislikes from all attendees of an event"""
        # Get all confirmed attendees
        responses = self.get_confirmed_attendees(event_id)
        attendee_phones = [r['respondent_phone'] for r in responses]
        
        # Get organizer phone
        event = self.get_event(event_id)
        if event:
            attendee_phones.append(event.get('organizer_phone'))
        
        # Get all dislikes from these users
        all_dislikes = []
        for phone in attendee_phones:
            dislikes = self.get_user_dislikes(phone)
            all_dislikes.extend(dislikes)
        
        return all_dislikes
    
    def update_dislike(self, dislike_id, update_data):
        """Update dislike"""
        doc_ref = self.db.collection('restaurant_dislikes').document(dislike_id)
        doc_ref.update(update_data)
        return doc_ref.get().to_dict()
    
    def delete_dislike(self, dislike_id):
        """Delete or deactivate dislike"""
        doc_ref = self.db.collection('restaurant_dislikes').document(dislike_id)
        doc_ref.update({'is_active': False})
    
    # ==================== RESTAURANT RECOMMENDATIONS ====================
    
    def save_recommendations(self, event_id, recommendations_data):
        """Save AI-generated recommendations"""
        doc_ref = self.db.collection('restaurant_recommendations').document()
        recommendation_id = doc_ref.id
        recommendations_data['event_id'] = event_id
        recommendations_data['generated_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(recommendations_data)
        result = doc_ref.get().to_dict()
        result['id'] = recommendation_id
        return result
    
    def get_recommendations(self, event_id):
        """Get recommendations for an event"""
        docs = self.db.collection('restaurant_recommendations').where('event_id', '==', event_id).order_by('generated_at', direction=firestore.Query.DESCENDING).limit(1).stream()
        for doc in docs:
            return doc.to_dict()
        return None
    
    # ==================== BOOKINGS ====================
    
    def create_booking(self, booking_data):
        """Create a booking"""
        doc_ref = self.db.collection('bookings').document()
        booking_id = doc_ref.id
        if 'booking_status' not in booking_data:
            booking_data['booking_status'] = 'pending'
        if 'calendar_invites_sent' not in booking_data:
            booking_data['calendar_invites_sent'] = False
        if 'calendar_event_ids' not in booking_data:
            booking_data['calendar_event_ids'] = []
        booking_data['booked_at'] = firestore.SERVER_TIMESTAMP
        booking_data['updated_at'] = firestore.SERVER_TIMESTAMP
        booking_data['completed_at'] = None
        doc_ref.set(booking_data)
        booking = doc_ref.get().to_dict()
        booking['id'] = booking_id
        return booking
    
    def get_booking(self, booking_id):
        """Get booking by ID"""
        doc = self.db.collection('bookings').document(booking_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    def get_event_booking(self, event_id):
        """Get booking for an event"""
        docs = self.db.collection('bookings').where('event_id', '==', event_id).order_by('booked_at', direction=firestore.Query.DESCENDING).limit(1).stream()
        for doc in docs:
            booking = doc.to_dict()
            booking['id'] = doc.id
            return booking
        return None
    
    def update_booking(self, booking_id, update_data):
        """Update booking"""
        doc_ref = self.db.collection('bookings').document(booking_id)
        update_data['updated_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.update(update_data)
        return doc_ref.get().to_dict()
    
    def complete_booking(self, booking_id):
        """Mark booking as completed"""
        doc_ref = self.db.collection('bookings').document(booking_id)
        doc_ref.update({
            'booking_status': 'completed',
            'completed_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return doc_ref.get().to_dict()
    
    # ==================== POST-EVENT REVIEWS ====================
    
    def create_review(self, review_data):
        """Create a post-event review"""
        # Check if review already exists
        existing = self.db.collection('post_event_reviews').where('event_id', '==', review_data['event_id']).where('reviewer_phone', '==', review_data['reviewer_phone']).stream()
        existing_doc = None
        for doc in existing:
            existing_doc = doc
            break
        
        if existing_doc:
            # Update existing review
            doc_ref = self.db.collection('post_event_reviews').document(existing_doc.id)
            review_data['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.update(review_data)
            return doc_ref.get().to_dict()
        else:
            # Create new review
            doc_ref = self.db.collection('post_event_reviews').document()
            review_data['submitted_at'] = firestore.SERVER_TIMESTAMP
            review_data['updated_at'] = firestore.SERVER_TIMESTAMP
            doc_ref.set(review_data)
            return doc_ref.get().to_dict()
    
    def get_event_reviews(self, event_id):
        """Get all reviews for an event"""
        reviews = []
        docs = self.db.collection('post_event_reviews').where('event_id', '==', event_id).stream()
        for doc in docs:
            review = doc.to_dict()
            review['id'] = doc.id
            reviews.append(review)
        return reviews
    
    def get_restaurant_reviews(self, restaurant_name, restaurant_address):
        """Get all reviews for a restaurant"""
        reviews = []
        docs = self.db.collection('post_event_reviews').where('restaurant_name', '==', restaurant_name).where('restaurant_address', '==', restaurant_address).stream()
        for doc in docs:
            review = doc.to_dict()
            review['id'] = doc.id
            reviews.append(review)
        return reviews
    
    def update_aggregate_ratings(self, restaurant_name, restaurant_address):
        """Update or create aggregate ratings for a restaurant"""
        # Get all reviews for this restaurant
        reviews = self.get_restaurant_reviews(restaurant_name, restaurant_address)
        
        if not reviews:
            return None
        
        # Calculate aggregates
        total_reviews = len(reviews)
        overall_ratings = [r['overall_rating'] for r in reviews if r.get('overall_rating')]
        food_ratings = [r['food_quality_rating'] for r in reviews if r.get('food_quality_rating')]
        service_ratings = [r['service_rating'] for r in reviews if r.get('service_rating')]
        atmosphere_ratings = [r['atmosphere_rating'] for r in reviews if r.get('atmosphere_rating')]
        value_ratings = [r['value_rating'] for r in reviews if r.get('value_rating')]
        
        # Calculate averages
        avg_overall = sum(overall_ratings) / len(overall_ratings) if overall_ratings else 0
        avg_food = sum(food_ratings) / len(food_ratings) if food_ratings else 0
        avg_service = sum(service_ratings) / len(service_ratings) if service_ratings else 0
        avg_atmosphere = sum(atmosphere_ratings) / len(atmosphere_ratings) if atmosphere_ratings else 0
        avg_value = sum(value_ratings) / len(value_ratings) if value_ratings else 0
        
        # Rating distribution
        rating_dist = {str(i): 0 for i in range(1, 6)}
        for rating in overall_ratings:
            rating_dist[str(int(rating))] = rating_dist.get(str(int(rating)), 0) + 1
        
        # Recommendation counts
        would_recommend_yes = sum(1 for r in reviews if r.get('would_recommend') == 'yes')
        would_recommend_no = sum(1 for r in reviews if r.get('would_recommend') == 'no')
        would_recommend_maybe = sum(1 for r in reviews if r.get('would_recommend') == 'maybe')
        
        # Blacklist count
        total_blacklists = sum(1 for r in reviews if r.get('added_to_blacklist') == True)
        blacklist_percentage = (total_blacklists / total_reviews * 100) if total_reviews > 0 else 0
        
        # Dates
        review_dates = [r.get('submitted_at') for r in reviews if r.get('submitted_at')]
        first_review_date = min(review_dates) if review_dates else None
        last_review_date = max(review_dates) if review_dates else None
        
        # Create or update aggregate document
        doc_id = f"{restaurant_name}_{restaurant_address}".replace(' ', '_').replace('/', '_')
        doc_ref = self.db.collection('restaurant_aggregate_ratings').document(doc_id)
        
        aggregate_data = {
            'restaurant_name': restaurant_name,
            'restaurant_address': restaurant_address,
            'total_reviews': total_reviews,
            'average_overall_rating': round(avg_overall, 2),
            'average_food_rating': round(avg_food, 2) if avg_food > 0 else None,
            'average_service_rating': round(avg_service, 2) if avg_service > 0 else None,
            'average_atmosphere_rating': round(avg_atmosphere, 2) if avg_atmosphere > 0 else None,
            'average_value_rating': round(avg_value, 2) if avg_value > 0 else None,
            'rating_distribution': rating_dist,
            'would_recommend_yes': would_recommend_yes,
            'would_recommend_no': would_recommend_no,
            'would_recommend_maybe': would_recommend_maybe,
            'total_blacklists': total_blacklists,
            'blacklist_percentage': round(blacklist_percentage, 2),
            'first_review_date': first_review_date,
            'last_review_date': last_review_date,
            'last_updated': firestore.SERVER_TIMESTAMP
        }
        
        doc_ref.set(aggregate_data, merge=True)
        return doc_ref.get().to_dict()
    
    def get_aggregate_rating(self, restaurant_name, restaurant_address):
        """Get aggregate ratings for a restaurant"""
        doc_id = f"{restaurant_name}_{restaurant_address}".replace(' ', '_').replace('/', '_')
        doc = self.db.collection('restaurant_aggregate_ratings').document(doc_id).get()
        if doc.exists:
            return doc.to_dict()
        return None
    
    # ==================== AI AGENT LOGS ====================
    
    def log_ai_action(self, log_data):
        """Log AI agent action"""
        doc_ref = self.db.collection('ai_agent_logs').document()
        log_data['timestamp'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(log_data)
        return doc_ref.get().to_dict()
    
    def get_event_ai_logs(self, event_id):
        """Get AI logs for an event"""
        logs = []
        docs = self.db.collection('ai_agent_logs').where('event_id', '==', event_id).order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            log = doc.to_dict()
            log['id'] = doc.id
            logs.append(log)
        return logs

