"""
Configuration settings for the Restaurant Planner application
"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Firebase settings
    FIREBASE_CREDENTIALS_PATH = os.getenv('FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    FIREBASE_PROJECT_ID = os.getenv('FIREBASE_PROJECT_ID', '')
    
    # Langchain settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    LANGCHAIN_API_KEY = os.getenv('LANGCHAIN_API_KEY', '')
    
    # Application settings
    MAX_RESERVATION_DAYS_AHEAD = int(os.getenv('MAX_RESERVATION_DAYS_AHEAD', '90'))
    DEFAULT_RESERVATION_DURATION_MINUTES = int(os.getenv('DEFAULT_RESERVATION_DURATION_MINUTES', '120'))
    # Frontend URL for invitation links (set in .env for dev/staging/production)
    FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', '')

    # Debug settings
    DEBUG_PHONE_NUMBER = os.getenv('DEBUG_PHONE_NUMBER', '+32 483 71 58 62')
    USE_DEBUG_PHONE = os.getenv('USE_DEBUG_PHONE', 'True').lower() == 'true'

    # ElevenLabs settings
    ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')
    ELEVENLABS_AGENT_ID = os.getenv('ELEVENLABS_AGENT_ID', '')
    ELEVENLABS_PHONE_NUMBER_ID = os.getenv('ELEVENLABS_PHONE_NUMBER_ID', '')

