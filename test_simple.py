"""
DEPRECATED: This test script is for the old restaurant management system.

The system has been rebuilt according to the design document (restaurant_planner_design_v2.pdf).
This file is kept for reference only.

Use test_event_flow.py instead, which tests the event planning flow.
"""
import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:5000/api"

print("Testing Restaurant Planner API...")
print("=" * 50)

# 1. Health check
print("\n1. Health Check")
try:
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.json()}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    print("   Make sure the Flask server is running: python app.py")
    exit(1)

# 2. Create restaurant
print("\n2. Creating Restaurant...")
restaurant_data = {
    "name": "Test Restaurant",
    "address": "123 Test St",
    "phone": "+1234567890",
    "email": "test@restaurant.com"
}
response = requests.post(f"{BASE_URL}/restaurants", json=restaurant_data)
print(f"   Status: {response.status_code}")
if response.status_code == 201:
    restaurant_id = response.json().get('restaurant_id')
    print(f"   ✅ Restaurant created! ID: {restaurant_id}")
    
    # 3. Get restaurant
    print(f"\n3. Getting Restaurant {restaurant_id}...")
    response = requests.get(f"{BASE_URL}/restaurants/{restaurant_id}")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✅ Restaurant retrieved!")
        print(f"   Name: {response.json().get('name')}")
    
    # 4. Create menu
    print(f"\n4. Creating Menu...")
    menu_data = {
        "name": "Test Menu",
        "items": [
            {
                "name": "Test Item",
                "description": "A test menu item",
                "price": 10.99,
                "category": "Main Course"
            }
        ]
    }
    response = requests.post(f"{BASE_URL}/menus/{restaurant_id}", json=menu_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        menu_id = response.json().get('menu_id')
        print(f"   ✅ Menu created! ID: {menu_id}")
    
    # 5. Create reservation
    print(f"\n5. Creating Reservation...")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    reservation_data = {
        "customer_name": "Test Customer",
        "customer_email": "customer@test.com",
        "customer_phone": "+1234567890",
        "date": tomorrow,
        "time": "19:00",
        "party_size": 2
    }
    response = requests.post(f"{BASE_URL}/reservations/{restaurant_id}", json=reservation_data)
    print(f"   Status: {response.status_code}")
    if response.status_code == 201:
        reservation_id = response.json().get('reservation_id')
        print(f"   ✅ Reservation created! ID: {reservation_id}")
    
    print("\n" + "=" * 50)
    print("✅ All tests passed!")
    print(f"\nCheck Firestore for restaurant ID: {restaurant_id}")
    print("=" * 50)
else:
    print(f"   ❌ Failed: {response.text}")

