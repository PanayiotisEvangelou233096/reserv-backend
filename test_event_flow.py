"""
Test script for Restaurant Planner v2 - Event Planning Flow
Tests the complete flow according to the design document
"""
import requests
import json
from datetime import datetime, timedelta
from dateutil import parser

BASE_URL = "http://localhost:5000/api"

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_response(response, title=""):
    """Print response details"""
    print(f"\n{title}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
        return response.status_code in [200, 201]
    except:
        print(f"Response: {response.text}")
        return False

def test_health_check():
    """Test health check endpoint"""
    print_section("1. Health Check")
    response = requests.get(f"{BASE_URL}/health")
    return print_response(response, "Health Check:")

def test_user_onboarding(phone_number):
    """Test user onboarding"""
    print_section("2. User Onboarding")
    
    user_data = {
        "phone_number": phone_number,
        "email": f"user{phone_number}@example.com",
        "dietary_restrictions": ["vegetarian", "gluten-free"],
        "alcohol_preference": "alcoholic",
        "push_notifications_enabled": True,
        "email_notifications_enabled": True
    }
    
    response = requests.post(
        f"{BASE_URL}/users/onboarding",
        json=user_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "User Onboarding:"):
        data = response.json()
        print(f"\n✅ User created: {phone_number}")
        return True
    return False

def test_get_user(phone_number):
    """Test getting user"""
    print_section("3. Get User")
    response = requests.get(f"{BASE_URL}/users/{phone_number}")
    return print_response(response, "Get User:")

def test_create_event(organizer_phone):
    """Test creating an event"""
    print_section("4. Create Event")
    
    # Create date for tomorrow
    tomorrow = datetime.now() + timedelta(days=1)
    preferred_date = tomorrow.isoformat()
    
    event_data = {
        "organizer_phone": organizer_phone,
        "organizer_email": f"{organizer_phone}@example.com",
        "location": "Amsterdam Centre",
        "occasion_description": "Birthday dinner",
        "expected_attendee_count": 4,
        "preferred_date": preferred_date,
        "preferred_time_slots": ["18:00-20:00", "19:00-21:00"]
    }
    
    response = requests.post(
        f"{BASE_URL}/events",
        json=event_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Create Event:"):
        data = response.json()
        event = data.get('event', {})
        event_id = event.get('event_id')
        invitation_link = event.get('invitation_link')
        print(f"\n✅ Event created with ID: {event_id}")
        print(f"✅ Invitation link: {invitation_link}")
        return event_id, invitation_link
    return None, None

def test_get_event(event_id):
    """Test getting event"""
    print_section("5. Get Event")
    response = requests.get(f"{BASE_URL}/events/{event_id}")
    return print_response(response, "Get Event:")

def test_submit_event_response(event_id, attendee_phone, is_new_user=False):
    """Test submitting event response"""
    print_section(f"6. Submit Event Response ({'New User' if is_new_user else 'Existing User'})")
    
    response_data = {
        "respondent_phone": attendee_phone,
        "email": f"{attendee_phone}@example.com",
        "attendance_confirmed": True,
        "location_preference_override": None,
        "event_specific_dietary_notes": None
    }
    
    # If new user, include onboarding data
    if is_new_user:
        response_data.update({
            "dietary_restrictions": ["vegan"],
            "alcohol_preference": "non-alcoholic"
        })
    
    response = requests.post(
        f"{BASE_URL}/events/{event_id}/responses",
        json=response_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Submit Response:"):
        print(f"\n✅ Response submitted for {attendee_phone}")
        return True
    return False

def test_get_event_responses(event_id):
    """Test getting event responses"""
    print_section("7. Get Event Responses")
    response = requests.get(f"{BASE_URL}/events/{event_id}/responses")
    return print_response(response, "Get Event Responses:")

def test_generate_recommendations(event_id):
    """Test generating AI recommendations"""
    print_section("8. Generate AI Recommendations")
    
    response = requests.post(
        f"{BASE_URL}/ai-agent/events/{event_id}/generate-recommendations",
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Generate Recommendations:"):
        data = response.json()
        recommendations = data.get('recommendations', {})
        recs = recommendations.get('recommendations', [])
        print(f"\n✅ Generated {len(recs)} recommendations")
        for rec in recs:
            print(f"   - {rec.get('rank')}. {rec.get('restaurant_name')} ({rec.get('cuisine_type')})")
        return True
    return False

def test_get_recommendations(event_id):
    """Test getting recommendations"""
    print_section("9. Get Recommendations")
    response = requests.get(f"{BASE_URL}/ai-agent/events/{event_id}/recommendations")
    return print_response(response, "Get Recommendations:")

def test_book_restaurant(event_id, recommendation_rank=1):
    """Test booking a restaurant"""
    print_section("10. Book Restaurant")
    
    booking_data = {
        "recommendation_rank": recommendation_rank,
        "booking_time": "19:00"
    }
    
    response = requests.post(
        f"{BASE_URL}/events/{event_id}/book",
        json=booking_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Book Restaurant:"):
        data = response.json()
        booking = data.get('booking', {})
        booking_id = booking.get('id')
        print(f"\n✅ Restaurant booked! Booking ID: {booking_id}")
        print(f"   Restaurant: {booking.get('restaurant_name')}")
        print(f"   Date: {booking.get('booking_date')}")
        print(f"   Time: {booking.get('booking_time')}")
        print(f"   Party Size: {booking.get('party_size')}")
        return booking_id
    return None

def test_get_booking(booking_id):
    """Test getting booking"""
    print_section("11. Get Booking")
    response = requests.get(f"{BASE_URL}/bookings/{booking_id}")
    return print_response(response, "Get Booking:")

def test_complete_booking(booking_id):
    """Test completing booking"""
    print_section("12. Complete Booking")
    response = requests.patch(f"{BASE_URL}/bookings/{booking_id}/complete")
    return print_response(response, "Complete Booking:")

def test_submit_review(event_id, reviewer_phone):
    """Test submitting a review"""
    print_section("13. Submit Review")
    
    review_data = {
        "reviewer_phone": reviewer_phone,
        "overall_rating": 4,
        "food_quality_rating": 5,
        "service_rating": 4,
        "atmosphere_rating": 4,
        "value_rating": 3,
        "would_recommend": "yes",
        "written_remarks": "Great food and service! Would definitely come back.",
        "added_to_blacklist": False
    }
    
    response = requests.post(
        f"{BASE_URL}/events/{event_id}/reviews",
        json=review_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Submit Review:"):
        print(f"\n✅ Review submitted by {reviewer_phone}")
        return True
    return False

def test_get_event_reviews(event_id):
    """Test getting event reviews"""
    print_section("14. Get Event Reviews")
    response = requests.get(f"{BASE_URL}/events/{event_id}/reviews")
    return print_response(response, "Get Event Reviews:")

def test_add_dislike(phone_number):
    """Test adding restaurant to blacklist"""
    print_section("15. Add Restaurant Dislike")
    
    dislike_data = {
        "restaurant_name": "The Gourmet Kitchen",
        "restaurant_address": "Amsterdam Centre, Main Street 123",
        "dislike_type": "permanent",
        "reason": "poor_food",
        "notes": "Food was not fresh"
    }
    
    response = requests.post(
        f"{BASE_URL}/users/{phone_number}/dislikes",
        json=dislike_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Add Dislike:"):
        print(f"\n✅ Restaurant added to blacklist")
        return True
    return False

def test_get_user_dislikes(phone_number):
    """Test getting user dislikes"""
    print_section("16. Get User Dislikes")
    response = requests.get(f"{BASE_URL}/users/{phone_number}/dislikes")
    return print_response(response, "Get User Dislikes:")

def main():
    """Run the complete test flow"""
    print("\n" + "=" * 60)
    print("  RESTAURANT PLANNER v2 - EVENT PLANNING TEST FLOW")
    print("=" * 60)
    print("\nThis test follows the design document flow:")
    print("1. User Onboarding")
    print("2. Event Creation")
    print("3. Guest Responses")
    print("4. AI Recommendations")
    print("5. Restaurant Booking")
    print("6. Post-Event Reviews")
    print("\nMake sure the Flask server is running on http://localhost:5000")
    print("Press Enter to continue or Ctrl+C to cancel...")
    input()
    
    # Test phone numbers
    organizer_phone = "+31612345678"
    attendee1_phone = "+31612345679"
    attendee2_phone = "+31612345680"
    
    # 1. Health check
    if not test_health_check():
        print("\n❌ Health check failed. Is the server running?")
        return
    
    # 2. User onboarding (organizer)
    if not test_user_onboarding(organizer_phone):
        print("\n❌ Failed to create organizer. Stopping tests.")
        return
    
    # 3. Get user
    test_get_user(organizer_phone)
    
    # 4. Create event
    event_id, invitation_link = test_create_event(organizer_phone)
    if not event_id:
        print("\n❌ Failed to create event. Stopping tests.")
        return
    
    # 5. Get event
    test_get_event(event_id)
    
    # 6. Submit responses (existing user)
    test_submit_event_response(event_id, attendee1_phone, is_new_user=False)
    
    # 7. Submit response (new user - will create user during response)
    test_submit_event_response(event_id, attendee2_phone, is_new_user=True)
    
    # 8. Get event responses
    test_get_event_responses(event_id)
    
    # 9. Generate recommendations
    if not test_generate_recommendations(event_id):
        print("\n⚠️  Failed to generate recommendations. Continuing anyway...")
    
    # 10. Get recommendations
    test_get_recommendations(event_id)
    
    # 11. Book restaurant
    booking_id = test_book_restaurant(event_id, recommendation_rank=1)
    if booking_id:
        # 12. Get booking
        test_get_booking(booking_id)
        
        # 13. Complete booking
        test_complete_booking(booking_id)
        
        # 14. Submit reviews
        test_submit_review(event_id, organizer_phone)
        test_submit_review(event_id, attendee1_phone)
        
        # 15. Get event reviews
        test_get_event_reviews(event_id)
    
    # 16. Test blacklist functionality
    test_add_dislike(organizer_phone)
    test_get_user_dislikes(organizer_phone)
    
    # Summary
    print_section("TEST SUMMARY")
    print(f"✅ Event ID: {event_id}")
    print(f"✅ Invitation Link: {invitation_link}")
    if booking_id:
        print(f"✅ Booking ID: {booking_id}")
    
    print("\n" + "=" * 60)
    print("  VERIFY IN FIRESTORE")
    print("=" * 60)
    print("\nTo verify the data in Firestore:")
    print("1. Go to Firebase Console: https://console.firebase.google.com/")
    print("2. Select your project")
    print("3. Go to Firestore Database")
    print("4. Check the following collections:")
    print("   - users (phone numbers as document IDs)")
    print("   - events")
    print("   - event_responses")
    print("   - restaurant_recommendations")
    print("   - bookings")
    print("   - post_event_reviews")
    print("   - restaurant_dislikes")
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

