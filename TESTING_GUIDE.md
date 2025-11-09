# Testing Guide

This guide will help you test the Restaurant Planner API and verify data in Firestore.

## Prerequisites

1. Flask server is running: `python app.py`
2. Firebase is configured (see `FIREBASE_SETUP.md`)
3. All dependencies installed: `pip install -r requirements.txt`

## Quick Test

Run the simple test script:

```bash
python test_simple.py
```

This will:
- Test health check
- Create a restaurant
- Get the restaurant
- Create a menu
- Create a reservation

## Complete Test Flow

Run the comprehensive test script:

```bash
python test_api_flow.py
```

This will:
1. ✅ Health check
2. ✅ Create restaurant
3. ✅ Get restaurant
4. ✅ Create menu with items
5. ✅ Create multiple tables
6. ✅ Create staff members
7. ✅ Create multiple reservations
8. ✅ Get reservations
9. ✅ Test analytics endpoints
10. ✅ Get all restaurant data

## Manual Testing with cURL

### 1. Health Check
```bash
curl http://localhost:5000/api/health
```

### 2. Create Restaurant
```bash
curl -X POST http://localhost:5000/api/restaurants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "The Gourmet Kitchen",
    "address": "123 Main St",
    "phone": "+1234567890",
    "email": "info@restaurant.com"
  }'
```

Save the `restaurant_id` from the response.

### 3. Create Menu
```bash
curl -X POST http://localhost:5000/api/menus/RESTAURANT_ID \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Dinner Menu",
    "items": [
      {
        "name": "Grilled Salmon",
        "description": "Fresh Atlantic salmon",
        "price": 24.99,
        "category": "Main Course"
      }
    ]
  }'
```

### 4. Create Table
```bash
curl -X POST http://localhost:5000/api/tables/RESTAURANT_ID \
  -H "Content-Type: application/json" \
  -d '{
    "table_number": 1,
    "capacity": 4,
    "location": "Window"
  }'
```

### 5. Create Staff
```bash
curl -X POST http://localhost:5000/api/staff/RESTAURANT_ID \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Smith",
    "email": "john@restaurant.com",
    "role": "Manager"
  }'
```

### 6. Create Reservation
```bash
curl -X POST http://localhost:5000/api/reservations/RESTAURANT_ID \
  -H "Content-Type: application/json" \
  -d '{
    "customer_name": "John Doe",
    "customer_email": "john@example.com",
    "customer_phone": "+1234567890",
    "date": "2024-01-15",
    "time": "19:00",
    "party_size": 4
  }'
```

### 7. Get All Data
```bash
# Get restaurant
curl http://localhost:5000/api/restaurants/RESTAURANT_ID

# Get menus
curl http://localhost:5000/api/menus/RESTAURANT_ID

# Get tables
curl http://localhost:5000/api/tables/RESTAURANT_ID

# Get staff
curl http://localhost:5000/api/staff/RESTAURANT_ID

# Get reservations
curl http://localhost:5000/api/reservations/RESTAURANT_ID

# Get reservations for specific date
curl "http://localhost:5000/api/reservations/RESTAURANT_ID?date=2024-01-15"
```

## Verifying Data in Firestore

### Step 1: Open Firebase Console
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project

### Step 2: Navigate to Firestore
1. Click on **"Firestore Database"** in the left sidebar
2. You should see the **"Data"** tab

### Step 3: View Your Data
1. You'll see a collection called **`restaurants`**
2. Click on a restaurant document (identified by its ID)
3. You'll see the restaurant data and subcollections:
   - **`menus`** - Contains all menus for this restaurant
   - **`tables`** - Contains all tables
   - **`staff`** - Contains all staff members
   - **`reservations`** - Contains all reservations

### Step 4: Explore Subcollections
1. Click on a subcollection (e.g., `menus`)
2. You'll see all menu documents
3. Click on a menu document to see its details
4. Repeat for other subcollections

### Expected Data Structure

```
restaurants/
  └── {restaurant_id}/
      ├── (restaurant fields: name, address, phone, email, etc.)
      ├── menus/
      │   └── {menu_id}/
      │       └── (menu fields: name, items, etc.)
      ├── tables/
      │   └── {table_id}/
      │       └── (table fields: table_number, capacity, etc.)
      ├── staff/
      │   └── {staff_id}/
      │       └── (staff fields: name, email, role, etc.)
      └── reservations/
          └── {reservation_id}/
              └── (reservation fields: customer_name, date, time, etc.)
```

## Testing Tips

### 1. Check Server Logs
Watch the Flask server console for:
- ✅ "Firebase initialized successfully"
- ✅ Request logs
- ❌ Any error messages

### 2. Use Postman or Insomnia
Instead of cURL, you can use:
- [Postman](https://www.postman.com/)
- [Insomnia](https://insomnia.rest/)

Import the endpoints and test interactively.

### 3. Verify Timestamps
All documents should have:
- `created_at` - When the document was created
- `updated_at` - When the document was last updated

These are automatically added by Firestore.

### 4. Test Error Cases
Try invalid requests:
```bash
# Missing required field
curl -X POST http://localhost:5000/api/restaurants \
  -H "Content-Type: application/json" \
  -d '{"name": "Test"}'

# Invalid restaurant ID
curl http://localhost:5000/api/restaurants/invalid-id
```

## Troubleshooting

### Data Not Appearing in Firestore
1. Check server logs for errors
2. Verify Firebase credentials are correct
3. Check Firestore security rules allow writes
4. Wait a few seconds - Firestore may have slight delay

### Connection Errors
1. Make sure Flask server is running
2. Check the port (default: 5000)
3. Verify BASE_URL in test scripts matches your server

### Firebase Errors
1. Verify `firebase-credentials.json` exists
2. Check the file path in `.env`
3. Ensure Firestore is enabled in Firebase Console
4. Check Firestore security rules

## Next Steps

After successful testing:
1. ✅ Verify all data appears in Firestore
2. ✅ Test all endpoints work correctly
3. ✅ Implement Langchain integration
4. ✅ Build your frontend
5. ✅ Add authentication (if needed)

## Test Scripts

- `test_simple.py` - Quick minimal test
- `test_api_flow.py` - Complete comprehensive test
- `test_setup.py` - Verify Firebase setup

Run them in order:
1. First: `python test_setup.py` (verify setup)
2. Then: `python test_simple.py` (quick test)
3. Finally: `python test_api_flow.py` (full test)

