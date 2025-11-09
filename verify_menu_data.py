"""
Verify Menu Data in Firestore
This script retrieves and displays menu data to verify it's saved correctly
"""
import requests
import json

BASE_URL = "http://localhost:5000/api"

def print_menu_data(menu):
    """Pretty print menu data"""
    print("\n" + "=" * 60)
    print("MENU DATA")
    print("=" * 60)
    print(f"Menu ID: {menu.get('id', 'N/A')}")
    print(f"Name: {menu.get('name', 'N/A')}")
    print(f"Description: {menu.get('description', 'N/A')}")
    print(f"Restaurant ID: {menu.get('restaurant_id', 'N/A')}")
    print(f"\nItems ({len(menu.get('items', []))}):")
    print("-" * 60)
    
    for i, item in enumerate(menu.get('items', []), 1):
        print(f"\n  Item {i}:")
        print(f"    Name: {item.get('name', 'N/A')}")
        print(f"    Description: {item.get('description', 'N/A')}")
        print(f"    Price: ${item.get('price', 'N/A')}")
        print(f"    Category: {item.get('category', 'N/A')}")
        if item.get('dietary_info'):
            print(f"    Dietary Info: {', '.join(item.get('dietary_info', []))}")
    
    print("\n" + "=" * 60)

def main():
    print("\n" + "=" * 60)
    print("  VERIFY MENU DATA IN FIRESTORE")
    print("=" * 60)
    
    # Get restaurant ID from user
    restaurant_id = input("\nEnter Restaurant ID (or press Enter to list all restaurants): ").strip()
    
    if not restaurant_id:
        # List all restaurants
        print("\nFetching all restaurants...")
        response = requests.get(f"{BASE_URL}/restaurants")
        if response.status_code == 200:
            restaurants = response.json().get('restaurants', [])
            if restaurants:
                print(f"\nFound {len(restaurants)} restaurant(s):")
                for i, restaurant in enumerate(restaurants, 1):
                    print(f"  {i}. {restaurant.get('name', 'N/A')} (ID: {restaurant.get('id', 'N/A')})")
                restaurant_id = input("\nEnter Restaurant ID: ").strip()
            else:
                print("No restaurants found. Please create one first.")
                return
        else:
            print(f"Error: {response.text}")
            return
    
    # Get menus for the restaurant
    print(f"\nFetching menus for restaurant {restaurant_id}...")
    response = requests.get(f"{BASE_URL}/menus/{restaurant_id}")
    
    if response.status_code == 200:
        data = response.json()
        menus = data.get('menus', [])
        
        if not menus:
            print(f"\n❌ No menus found for restaurant {restaurant_id}")
            print("\nTo create a menu, use:")
            print(f"  curl -X POST {BASE_URL}/menus/{restaurant_id} \\")
            print("    -H 'Content-Type: application/json' \\")
            print("    -d '{\"name\": \"Test Menu\", \"items\": [{\"name\": \"Item 1\", \"price\": 10.99, \"category\": \"Main\"}]}'")
            return
        
        print(f"\n✅ Found {len(menus)} menu(s):")
        
        for i, menu in enumerate(menus, 1):
            print_menu_data(menu)
            
            # Ask if user wants to see raw JSON
            show_json = input(f"\nShow raw JSON for menu {i}? (y/n): ").strip().lower()
            if show_json == 'y':
                print("\nRaw JSON:")
                print(json.dumps(menu, indent=2, default=str))
        
        print("\n" + "=" * 60)
        print("HOW TO VIEW IN FIRESTORE CONSOLE:")
        print("=" * 60)
        print("\n1. Go to Firebase Console: https://console.firebase.google.com/")
        print("2. Select your project")
        print("3. Go to Firestore Database")
        print(f"4. Navigate to: restaurants → {restaurant_id} → menus")
        print("5. You'll see a list of menu document IDs")
        print("6. CLICK on a menu document ID to see its fields:")
        print("   - name")
        print("   - description")
        print("   - items (array with all menu items)")
        print("   - restaurant_id")
        print("   - created_at")
        print("   - updated_at")
        print("\n⚠️  IMPORTANT: You need to click on the document ID to see the data!")
        print("   Just seeing the ID list doesn't show the actual data.")
        print("=" * 60)
        
    else:
        print(f"\n❌ Error fetching menus: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 404:
            print(f"\nRestaurant {restaurant_id} not found.")
            print("Make sure the restaurant ID is correct.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except requests.exceptions.ConnectionError:
        print("\n❌ Connection error. Make sure the Flask server is running:")
        print("   python app.py")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

