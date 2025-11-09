"""
Test script to verify Firebase setup
Run this after setting up Firebase to check if everything is configured correctly
"""
import os
import sys
from dotenv import load_dotenv

def test_environment():
    """Test if environment variables are set"""
    print("Testing environment variables...")
    load_dotenv()
    
    required_vars = [
        'FIREBASE_CREDENTIALS_PATH',
        'FIREBASE_PROJECT_ID'
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            print(f"  ❌ {var} is not set")
        else:
            print(f"  ✅ {var} = {value}")
    
    if missing:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing)}")
        return False
    
    return True

def test_credentials_file():
    """Test if Firebase credentials file exists"""
    print("\nTesting Firebase credentials file...")
    load_dotenv()
    
    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    
    if os.path.exists(cred_path):
        print(f"  ✅ Credentials file found: {cred_path}")
        
        # Check if it's a valid JSON
        try:
            import json
            with open(cred_path, 'r') as f:
                cred_data = json.load(f)
            
            required_keys = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            missing_keys = [key for key in required_keys if key not in cred_data]
            
            if missing_keys:
                print(f"  ⚠️  Missing keys in credentials file: {', '.join(missing_keys)}")
                return False
            else:
                print(f"  ✅ Credentials file is valid")
                print(f"  ✅ Project ID: {cred_data.get('project_id', 'N/A')}")
                return True
        except json.JSONDecodeError:
            print(f"  ❌ Credentials file is not valid JSON")
            return False
    else:
        print(f"  ❌ Credentials file not found: {cred_path}")
        print(f"     Please download it from Firebase Console and place it in the backend folder")
        return False

def test_firebase_connection():
    """Test Firebase connection"""
    print("\nTesting Firebase connection...")
    
    try:
        from firebase_service import FirebaseService
        firebase_service = FirebaseService()
        print("  ✅ Firebase connection successful")
        return True
    except FileNotFoundError as e:
        print(f"  ❌ {str(e)}")
        return False
    except Exception as e:
        print(f"  ❌ Firebase connection failed: {str(e)}")
        return False

def test_dependencies():
    """Test if required dependencies are installed"""
    print("\nTesting dependencies...")
    
    required_packages = [
        'flask',
        'flask_cors',
        'firebase_admin',
        'dotenv'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"  ✅ {package} installed")
        except ImportError:
            missing.append(package)
            print(f"  ❌ {package} not installed")
    
    if missing:
        print(f"\n⚠️  Missing packages: {', '.join(missing)}")
        print(f"   Run: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Run all tests"""
    print("=" * 50)
    print("Firebase Setup Verification")
    print("=" * 50)
    
    results = []
    
    # Test dependencies
    results.append(("Dependencies", test_dependencies()))
    
    # Test environment
    results.append(("Environment Variables", test_environment()))
    
    # Test credentials file
    results.append(("Credentials File", test_credentials_file()))
    
    # Test Firebase connection (only if previous tests passed)
    if all([r[1] for r in results[:-1]]):
        results.append(("Firebase Connection", test_firebase_connection()))
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name}: {status}")
    
    all_passed = all([r[1] for r in results])
    
    if all_passed:
        print("\n🎉 All tests passed! Your setup is correct.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())

