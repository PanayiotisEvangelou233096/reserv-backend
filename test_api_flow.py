"""
DEPRECATED: This test script is for the old restaurant management system.

The system has been rebuilt according to the design document (restaurant_planner_design_v2.pdf).
This file is kept for reference only.

Use test_event_flow.py instead, which tests the event planning flow:
- User onboarding
- Event creation
- Guest responses
- AI recommendations
- Restaurant booking
- Post-event reviews
"""
import requests
import json
import time
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000/api"

def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_response(response, description):
    """Print formatted response"""
    print(f"\n{description}")
    print(f"Status: {response.status_code}")
    if response.status_code < 400:
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"Error: {response.text}")
    return response.status_code < 400

def test_health_check():
    """Test health check endpoint"""
    print_section("1. Health Check")
    response = requests.get(f"{BASE_URL}/health")
    return print_response(response, "Health Check:")

def test_create_restaurant():
    """Test creating a restaurant"""
    print_section("2. Create Restaurant")
    
    restaurant_data = {
        "name": "The Gourmet Kitchen",
        "address": "123 Main Street, New York, NY 10001",
        "phone": "+1-555-0123",
        "email": "info@gourmetkitchen.com",
        "cuisine_type": "Italian",
        "capacity": 50,
        "opening_hours": {
            "monday": "11:00-22:00",
            "tuesday": "11:00-22:00",
            "wednesday": "11:00-22:00",
            "thursday": "11:00-22:00",
            "friday": "11:00-23:00",
            "saturday": "11:00-23:00",
            "sunday": "12:00-21:00"
        }
    }
    
    response = requests.post(
        f"{BASE_URL}/restaurants",
        json=restaurant_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Create Restaurant:"):
        data = response.json()
        restaurant_id = data.get('restaurant_id')
        print(f"\n✅ Restaurant created with ID: {restaurant_id}")
        return restaurant_id
    return None

def test_get_restaurant(restaurant_id):
    """Test getting a restaurant"""
    print_section("3. Get Restaurant")
    response = requests.get(f"{BASE_URL}/restaurants/{restaurant_id}")
    print_response(response, f"Get Restaurant {restaurant_id}:")
    return response.status_code == 200

def test_create_menu(restaurant_id):
    """Test creating a menu"""
    print_section("4. Create Menu")
    
    menu_data = {
        "name": "Dinner Menu",
        "description": "Our signature dinner menu",
        "items": [
            {
                "name": "Grilled Salmon",
                "description": "Fresh Atlantic salmon with lemon butter sauce",
                "price": 24.99,
                "category": "Main Course",
                "dietary_info": ["gluten-free"]
            },
            {
                "name": "Margherita Pizza",
                "description": "Classic pizza with tomato, mozzarella, and basil",
                "price": 16.99,
                "category": "Main Course",
                "dietary_info": ["vegetarian"]
            },
            {
                "name": "Caesar Salad",
                "description": "Fresh romaine lettuce with Caesar dressing",
                "price": 12.99,
                "category": "Appetizer",
                "dietary_info": []
            },
            {
                "name": "Tiramisu",
                "description": "Classic Italian dessert",
                "price": 8.99,
                "category": "Dessert",
                "dietary_info": ["vegetarian"]
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/menus/{restaurant_id}",
        json=menu_data,
        headers={"Content-Type": "application/json"}
    )
    
    if print_response(response, "Create Menu:"):
        data = response.json()
        menu_id = data.get('menu_id')
        print(f"\n✅ Menu created with ID: {menu_id}")
        
        # Verify menu was saved by retrieving it
        print(f"\nVerifying menu data...")
        verify_response = requests.get(f"{BASE_URL}/menus/{restaurant_id}/{menu_id}")
        if verify_response.status_code == 200:
            menu_data = verify_response.json()
            print(f"✅ Menu verified! Name: {menu_data.get('name')}")
            print(f"   Items: {len(menu_data.get('items', []))} items")
            for i, item in enumerate(menu_data.get('items', []), 1):
                print(f"   {i}. {item.get('name')} - ${item.get('price')}")
        
        return menu_id
    return None

def test_create_tables(restaurant_id):
    """Test creating tables"""
    print_section("5. Create Tables")
    
    tables_data = [
        {"table_number": 1, "capacity": 2, "location": "Window", "status": "available"},
        {"table_number": 2, "capacity": 4, "location": "Window", "status": "available"},
        {"table_number": 3, "capacity": 4, "location": "Center", "status": "available"},
        {"table_number": 4, "capacity": 6, "location": "Center", "status": "available"},
        {"table_number": 5, "capacity": 8, "location": "Private", "status": "available"}
    ]
    
    table_ids = []
    for table_data in tables_data:
        response = requests.post(
            f"{BASE_URL}/tables/{restaurant_id}",
            json=table_data,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 201:
            data = response.json()
            table_id = data.get('table_id')
            table_ids.append(table_id)
            print(f"✅ Table {table_data['table_number']} created (ID: {table_id})")
        else:
            print(f"❌ Failed to create table {table_data['table_number']}: {response.text}")
    
    return table_ids

def test_create_staff(restaurant_id):
    """Test creating staff members"""
    print_section("6. Create Staff")
    
    staff_data = [
        {
            "name": "John Smith",
            "email": "john@gourmetkitchen.com",
            "phone": "+1-555-0101",
            "role": "Manager",
            "shift": "Day"
        },
        {
            "name": "Sarah Johnson",
            "email": "sarah@gourmetkitchen.com",
            "phone": "+1-555-0102",
            "role": "Server",
            "shift": "Evening"
        },
        {
            "name": "Mike Chen",
            "email": "mike@gourmetkitchen.com",
            "phone": "+1-555-0103",
            "role": "Chef",
            "shift": "Day"
        }
    ]
    
    staff_ids = []
    for staff in staff_data:
        response = requests.post(
            f"{BASE_URL}/staff/{restaurant_id}",
            json=staff,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 201:
            data = response.json()
            staff_id = data.get('staff_id')
            staff_ids.append(staff_id)
            print(f"✅ Staff {staff['name']} created (ID: {staff_id})")
        else:
            print(f"❌ Failed to create staff {staff['name']}: {response.text}")
    
    return staff_ids

def test_create_reservations(restaurant_id):
    """Test creating reservations"""
    print_section("7. Create Reservations")
    
    # Get tomorrow's date
    tomorrow = datetime.now() + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")
    
    reservations_data = [
        {
            "customer_name": "Alice Brown",
            "customer_email": "alice@example.com",
            "customer_phone": "+1-555-0201",
            "date": date_str,
            "time": "19:00",
            "party_size": 2,
            "special_requests": "Window seat preferred",
            "status": "confirmed"
        },
        {
            "customer_name": "Bob Wilson",
            "customer_email": "bob@example.com",
            "customer_phone": "+1-555-0202",
            "date": date_str,
            "time": "20:00",
            "party_size": 4,
            "special_requests": "Anniversary celebration",
            "status": "confirmed"
        },
        {
            "customer_name": "Carol Davis",
            "customer_email": "carol@example.com",
            "customer_phone": "+1-555-0203",
            "date": date_str,
            "time": "19:30",
            "party_size": 2,
            "special_requests": "",
            "status": "pending"
        }
    ]
    
    reservation_ids = []
    for reservation in reservations_data:
        response = requests.post(
            f"{BASE_URL}/reservations/{restaurant_id}",
            json=reservation,
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 201:
            data = response.json()
            reservation_id = data.get('reservation_id')
            reservation_ids.append(reservation_id)
            print(f"✅ Reservation for {reservation['customer_name']} created (ID: {reservation_id})")
        else:
            print(f"❌ Failed to create reservation: {response.text}")
    
    return reservation_ids, date_str

def test_get_reservations(restaurant_id, date):
    """Test getting reservations"""
    print_section("8. Get Reservations")
    response = requests.get(f"{BASE_URL}/reservations/{restaurant_id}?date={date}")
    print_response(response, f"Get Reservations for {date}:")
    return response.status_code == 200

def test_analytics(restaurant_id):
    """Test analytics endpoints"""
    print_section("9. Analytics")
    
    # Reservation analytics
    response = requests.get(f"{BASE_URL}/analytics/{restaurant_id}/reservations")
    print_response(response, "Reservation Analytics:")
    
    # Revenue analytics
    response = requests.get(f"{BASE_URL}/analytics/{restaurant_id}/revenue")
    print_response(response, "Revenue Analytics:")
    
    # Popular times
    response = requests.get(f"{BASE_URL}/analytics/{restaurant_id}/popular-times")
    print_response(response, "Popular Times:")

def test_get_all_data(restaurant_id):
    """Test getting all data for the restaurant"""
    print_section("10. Get All Restaurant Data")
    
    # Get menus
    response = requests.get(f"{BASE_URL}/menus/{restaurant_id}")
    if response.status_code == 200:
        menus = response.json().get('menus', [])
        print(f"✅ Found {len(menus)} menu(s)")
    
    # Get tables
    response = requests.get(f"{BASE_URL}/tables/{restaurant_id}")
    if response.status_code == 200:
        tables = response.json().get('tables', [])
        print(f"✅ Found {len(tables)} table(s)")
    
    # Get staff
    response = requests.get(f"{BASE_URL}/staff/{restaurant_id}")
    if response.status_code == 200:
        staff = response.json().get('staff', [])
        print(f"✅ Found {len(staff)} staff member(s)")
    
    # Get all reservations
    response = requests.get(f"{BASE_URL}/reservations/{restaurant_id}")
    if response.status_code == 200:
        reservations = response.json().get('reservations', [])
        print(f"✅ Found {len(reservations)} reservation(s)")

def main():
    """Run the complete test flow"""
    print("\n" + "=" * 60)
    print("  RESTAURANT PLANNER API - COMPLETE TEST FLOW")
    print("=" * 60)
    print("\nMake sure the Flask server is running on http://localhost:5000")
    print("Press Enter to continue or Ctrl+C to cancel...")
    input()
    
    # Test health check
    if not test_health_check():
        print("\n❌ Health check failed. Is the server running?")
        return
    
    # Test creating restaurant
    restaurant_id = test_create_restaurant()
    if not restaurant_id:
        print("\n❌ Failed to create restaurant. Stopping tests.")
        return
    
    # Wait a moment for Firestore to process
    time.sleep(1)
    
    # Test getting restaurant
    test_get_restaurant(restaurant_id)
    
    # Test creating menu
    menu_id = test_create_menu(restaurant_id)
    time.sleep(1)
    
    # Test creating tables
    table_ids = test_create_tables(restaurant_id)
    time.sleep(1)
    
    # Test creating staff
    staff_ids = test_create_staff(restaurant_id)
    time.sleep(1)
    
    # Test creating reservations
    reservation_ids, date = test_create_reservations(restaurant_id)
    time.sleep(1)
    
    # Test getting reservations
    test_get_reservations(restaurant_id, date)
    
    # Test analytics
    test_analytics(restaurant_id)
    
    # Test getting all data
    test_get_all_data(restaurant_id)
    
    # Summary
    print_section("TEST SUMMARY")
    print(f"✅ Restaurant ID: {restaurant_id}")
    print(f"✅ Menu ID: {menu_id}")
    print(f"✅ Tables created: {len(table_ids)}")
    print(f"✅ Staff created: {len(staff_ids)}")
    print(f"✅ Reservations created: {len(reservation_ids)}")
    
    print("\n" + "=" * 60)
    print("  VERIFY IN FIRESTORE")
    print("=" * 60)
    print("\nTo verify the data in Firestore:")
    print("1. Go to Firebase Console: https://console.firebase.google.com/")
    print("2. Select your project")
    print("3. Go to Firestore Database")
    print("4. You should see a collection called 'restaurants'")
    print(f"5. Click on restaurant ID: {restaurant_id}")
    print("6. You should see subcollections:")
    print("   - menus (with your menu)")
    print("   - tables (with your tables)")
    print("   - staff (with your staff members)")
    print("   - reservations (with your reservations)")
    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETED!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error. Make sure the Flask server is running:")
        print("   python app.py")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

