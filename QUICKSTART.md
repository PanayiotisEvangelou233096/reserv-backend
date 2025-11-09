# Quick Start Guide

## Prerequisites

- Python 3.8+
- Firebase account
- (Optional) OpenAI API key for Langchain features

## Installation Steps

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Up Firebase

Follow the detailed instructions in `FIREBASE_SETUP.md` or:

1. Create a Firebase project at [Firebase Console](https://console.firebase.google.com/)
2. Enable Firestore Database
3. Download service account key as `firebase-credentials.json`
4. Place `firebase-credentials.json` in the `backend` folder

### 3. Configure Environment

Create a `.env` file in the `backend` folder:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=your-firebase-project-id
OPENAI_API_KEY=your-openai-api-key
LANGCHAIN_API_KEY=your-langchain-api-key
MAX_RESERVATION_DAYS_AHEAD=90
DEFAULT_RESERVATION_DURATION_MINUTES=120
```

### 4. Run the Application

```bash
python app.py
```

The server will start on `http://localhost:5000`

### 5. Test the API

```bash
# Health check
curl http://localhost:5000/api/health

# Create a restaurant
curl -X POST http://localhost:5000/api/restaurants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Restaurant",
    "address": "123 Test St",
    "phone": "+1234567890",
    "email": "test@restaurant.com"
  }'
```

## Project Structure

```
backend/
├── app.py                    # Main Flask app
├── config.py                 # Configuration
├── firebase_service.py        # Firebase operations
├── langchain_integration.py   # Langchain (structure only)
├── routes/                    # API routes
│   ├── restaurant_routes.py
│   ├── menu_routes.py
│   ├── reservation_routes.py
│   ├── table_routes.py
│   ├── staff_routes.py
│   ├── analytics_routes.py
│   └── ai_routes.py
├── requirements.txt           # Dependencies
├── .env                       # Environment variables (create this)
├── firebase-credentials.json  # Firebase key (download from Firebase)
└── README.md                  # Full documentation
```

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py

# Run with debug mode (default)
FLASK_DEBUG=1 python app.py

# Check health
curl http://localhost:5000/api/health
```

## Next Steps

1. Set up Firebase (see `FIREBASE_SETUP.md`)
2. Test API endpoints
3. Implement Langchain integration (see `langchain_integration.py`)
4. Build your frontend to consume the API

