# Restaurant Planner Backend

A comprehensive Flask backend for restaurant planning and management with Firebase Firestore integration and Langchain AI capabilities.

## Features

- **Restaurant Management**: CRUD operations for restaurants
- **Menu Planning**: Create and manage menus with items
- **Reservation Management**: Handle bookings and reservations
- **Table Management**: Manage restaurant tables and capacity
- **Staff Management**: Manage restaurant staff
- **Analytics**: Get insights on reservations and revenue
- **AI Integration**: Langchain-powered recommendations and chat

## Setup Instructions

### 1. Prerequisites

- Python 3.8 or higher
- Firebase project with Firestore enabled
- OpenAI API key (for Langchain integration)

### 2. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Firebase Firestore Setup

#### Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click "Add project" or select an existing project
3. Follow the setup wizard to create your project

#### Step 2: Enable Firestore Database

1. In your Firebase project, go to "Firestore Database"
2. Click "Create database"
3. Choose "Start in production mode" (you can change rules later)
4. Select a location for your database
5. Click "Enable"

#### Step 3: Get Service Account Key

1. Go to Project Settings (gear icon) → Service Accounts
2. Click "Generate new private key"
3. Download the JSON file (this is your service account key)
4. Save it as `firebase-credentials.json` in the `backend` folder

#### Step 4: Configure Firestore Security Rules (Optional but Recommended)

Go to Firestore Database → Rules and update:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow read/write access to restaurants and their subcollections
    match /restaurants/{restaurantId} {
      allow read, write: if request.auth != null;
      match /menus/{menuId} {
        allow read, write: if request.auth != null;
      }
      match /reservations/{reservationId} {
        allow read, write: if request.auth != null;
      }
      match /tables/{tableId} {
        allow read, write: if request.auth != null;
      }
      match /staff/{staffId} {
        allow read, write: if request.auth != null;
      }
    }
  }
}
```

**Note**: For development, you can use more permissive rules, but for production, implement proper authentication.

#### Step 5: Update Environment Variables

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Update `.env` with your configuration:
   ```env
   FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
   FIREBASE_PROJECT_ID=your-firebase-project-id
   OPENAI_API_KEY=your-openai-api-key
   ```

### 4. Run the Application

```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Endpoints

### Restaurants
- `POST /api/restaurants` - Create restaurant
- `GET /api/restaurants` - Get all restaurants
- `GET /api/restaurants/<id>` - Get restaurant by ID
- `PUT /api/restaurants/<id>` - Update restaurant
- `DELETE /api/restaurants/<id>` - Delete restaurant

### Menus
- `POST /api/menus/<restaurant_id>` - Create menu
- `GET /api/menus/<restaurant_id>` - Get all menus
- `GET /api/menus/<restaurant_id>/<menu_id>` - Get menu by ID
- `PUT /api/menus/<restaurant_id>/<menu_id>` - Update menu
- `DELETE /api/menus/<restaurant_id>/<menu_id>` - Delete menu

### Reservations
- `POST /api/reservations/<restaurant_id>` - Create reservation
- `GET /api/reservations/<restaurant_id>` - Get all reservations (optional: ?date=YYYY-MM-DD)
- `GET /api/reservations/<restaurant_id>/<reservation_id>` - Get reservation by ID
- `PUT /api/reservations/<restaurant_id>/<reservation_id>` - Update reservation
- `DELETE /api/reservations/<restaurant_id>/<reservation_id>` - Delete reservation
- `POST /api/reservations/<restaurant_id>/<reservation_id>/confirm` - Confirm reservation
- `POST /api/reservations/<restaurant_id>/<reservation_id>/cancel` - Cancel reservation

### Tables
- `POST /api/tables/<restaurant_id>` - Create table
- `GET /api/tables/<restaurant_id>` - Get all tables
- `GET /api/tables/<restaurant_id>/<table_id>` - Get table by ID
- `PUT /api/tables/<restaurant_id>/<table_id>` - Update table
- `DELETE /api/tables/<restaurant_id>/<table_id>` - Delete table

### Staff
- `POST /api/staff/<restaurant_id>` - Create staff member
- `GET /api/staff/<restaurant_id>` - Get all staff
- `GET /api/staff/<restaurant_id>/<staff_id>` - Get staff by ID
- `PUT /api/staff/<restaurant_id>/<staff_id>` - Update staff
- `DELETE /api/staff/<restaurant_id>/<staff_id>` - Delete staff

### Analytics
- `GET /api/analytics/<restaurant_id>/reservations` - Get reservation analytics
- `GET /api/analytics/<restaurant_id>/revenue` - Get revenue analytics
- `GET /api/analytics/<restaurant_id>/popular-times` - Get popular reservation times

### AI
- `POST /api/ai/recommendations/menu` - Get menu recommendations
- `POST /api/ai/recommendations/reservation` - Get reservation recommendations
- `POST /api/ai/chat` - AI chat endpoint

## Example API Calls

### Create a Restaurant
```bash
curl -X POST http://localhost:5000/api/restaurants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "The Gourmet Kitchen",
    "address": "123 Main St",
    "phone": "+1234567890",
    "email": "info@gourmetkitchen.com"
  }'
```

### Create a Menu
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

### Create a Reservation
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

## Langchain Integration

The Langchain integration is set up in `langchain_integration.py`. You need to:

1. Install Langchain dependencies (already in requirements.txt)
2. Fill in the implementation in `langchain_integration.py`
3. Configure your OpenAI API key in `.env`

The structure is provided, but you'll need to implement the specific logic based on your requirements.

## Project Structure

```
backend/
├── app.py                 # Main Flask application
├── config.py              # Configuration settings
├── firebase_service.py     # Firebase Firestore service
├── langchain_integration.py  # Langchain AI integration (structure only)
├── routes/                # API route blueprints
│   ├── restaurant_routes.py
│   ├── menu_routes.py
│   ├── reservation_routes.py
│   ├── table_routes.py
│   ├── staff_routes.py
│   ├── analytics_routes.py
│   └── ai_routes.py
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .env.example          # Example environment variables
├── firebase-credentials.json  # Firebase service account key (not in git)
└── README.md             # This file
```

## Troubleshooting

### Firebase Connection Issues
- Ensure `firebase-credentials.json` is in the backend folder
- Verify the file path in `.env` matches the actual file location
- Check that Firestore is enabled in your Firebase project

### Import Errors
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.8 or higher

### Port Already in Use
- Change the port in `app.py`: `app.run(debug=True, host='0.0.0.0', port=5001)`

## Security Notes

- Never commit `firebase-credentials.json` or `.env` to version control
- Use environment variables for sensitive data
- Implement proper authentication for production use
- Configure Firestore security rules appropriately

## License

This project is part of the AISO Hackathon.

