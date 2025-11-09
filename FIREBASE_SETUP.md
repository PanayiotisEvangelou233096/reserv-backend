# Firebase Firestore Setup Guide

## Step-by-Step Instructions

### Step 1: Create a Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **"Add project"** or select an existing project
3. Enter your project name (e.g., "restaurant-planner")
4. Click **"Continue"**
5. (Optional) Enable Google Analytics
6. Click **"Create project"**
7. Wait for the project to be created, then click **"Continue"**

### Step 2: Enable Firestore Database

1. In your Firebase project dashboard, click on **"Firestore Database"** in the left sidebar
2. Click **"Create database"**
3. Choose **"Start in production mode"** (you can change rules later)
4. Select a location for your database (choose the closest to your users)
5. Click **"Enable"**
6. Wait for Firestore to be initialized

### Step 3: Get Service Account Key

1. Click on the **gear icon** (⚙️) next to "Project Overview" in the left sidebar
2. Select **"Project settings"**
3. Go to the **"Service accounts"** tab
4. Click **"Generate new private key"**
5. A dialog will appear - click **"Generate key"**
6. A JSON file will be downloaded - this is your service account key
7. **Rename the file** to `firebase-credentials.json`
8. **Move the file** to the `backend` folder

### Step 4: Configure Firestore Security Rules

1. In Firebase Console, go to **"Firestore Database"**
2. Click on the **"Rules"** tab
3. Replace the default rules with:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Allow read/write access to restaurants and their subcollections
    match /restaurants/{restaurantId} {
      allow read, write: if true; // For development - change in production
      
      match /menus/{menuId} {
        allow read, write: if true;
      }
      
      match /reservations/{reservationId} {
        allow read, write: if true;
      }
      
      match /tables/{tableId} {
        allow read, write: if true;
      }
      
      match /staff/{staffId} {
        allow read, write: if true;
      }
    }
  }
}
```

4. Click **"Publish"**

**⚠️ Important**: The rules above allow public read/write access. For production, implement proper authentication:
- Use Firebase Authentication
- Check `request.auth != null` for authenticated users
- Implement role-based access control

### Step 5: Update Environment Variables

1. In the `backend` folder, create a `.env` file (or copy from `.env.example`):

```bash
cd backend
cp .env.example .env
```

2. Open `.env` and update the following:

```env
# Firebase Configuration
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
FIREBASE_PROJECT_ID=your-firebase-project-id

# Langchain Configuration (optional for now)
OPENAI_API_KEY=your-openai-api-key
LANGCHAIN_API_KEY=your-langchain-api-key
```

3. To find your **Project ID**:
   - Go to Firebase Console
   - Click on the gear icon → Project settings
   - The Project ID is shown at the top of the General tab

### Step 6: Verify Setup

1. Make sure `firebase-credentials.json` is in the `backend` folder
2. Make sure `.env` file exists and has the correct paths
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Check the console for "Firebase initialized successfully"

### Step 7: Test the Connection

1. Start the Flask server
2. Make a test API call:

```bash
curl http://localhost:5000/api/health
```

Expected response:
```json
{
  "status": "healthy",
  "firebase_connected": true
}
```

## Troubleshooting

### Error: "Firebase credentials file not found"
- Ensure `firebase-credentials.json` is in the `backend` folder
- Check the file path in `.env` matches the actual location
- Verify the file name is exactly `firebase-credentials.json`

### Error: "Failed to initialize Firebase"
- Check that the service account key JSON is valid
- Verify the JSON file hasn't been corrupted
- Ensure you downloaded the key from the correct Firebase project

### Error: "Permission denied"
- Check Firestore security rules
- For development, use the permissive rules shown above
- For production, implement proper authentication

### Error: "Project not found"
- Verify your Project ID in `.env` matches your Firebase project
- Check that Firestore is enabled in your Firebase project

## Production Considerations

1. **Security Rules**: Implement proper authentication and authorization
2. **Service Account**: Use a service account with minimal required permissions
3. **Environment Variables**: Never commit `.env` or `firebase-credentials.json` to version control
4. **Firestore Indexes**: Create indexes for complex queries
5. **Backup**: Set up regular backups of your Firestore data
6. **Monitoring**: Enable Firebase monitoring and alerts

## Next Steps

After setting up Firebase:
1. Test creating a restaurant via API
2. Test creating menus and reservations
3. Implement Langchain integration
4. Set up authentication (if needed)
5. Deploy to production

