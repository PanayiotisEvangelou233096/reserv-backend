"""
User Management Routes
"""
from flask import Blueprint, request, jsonify, current_app
import logging

logger = logging.getLogger(__name__)
user_bp = Blueprint('users', __name__)

@user_bp.route('/onboarding', methods=['POST'])
def user_onboarding():
    """Create or update user preferences during onboarding"""
    try:
        data = request.get_json()
        
        # Validate required fields
        phone_number = data.get('phone_number')
        if not phone_number:
            return jsonify({'error': 'phone_number is required'}), 400
        
        # Validate dietary restrictions
        dietary_restrictions = data.get('dietary_restrictions', [])
        if not isinstance(dietary_restrictions, list):
            return jsonify({'error': 'dietary_restrictions must be a list'}), 400
        
        # Validate alcohol preference
        alcohol_preference = data.get('alcohol_preference')
        if alcohol_preference not in ['alcoholic', 'non-alcoholic', 'no-preference']:
            return jsonify({'error': 'alcohol_preference must be one of: alcoholic, non-alcoholic, no-preference'}), 400
        
        firebase_service = current_app.get_firebase_service()
        
        # Create or update user
        user_data = {
            'phone_number': phone_number,
            'email': data.get('email', ''),
            'dietary_restrictions': dietary_restrictions,
            'alcohol_preference': alcohol_preference,
            'push_notifications_enabled': data.get('push_notifications_enabled', True),
            'email_notifications_enabled': data.get('email_notifications_enabled', True)
        }
        
        user = firebase_service.create_or_update_user(phone_number, user_data)
        
        return jsonify({
            'message': 'User preferences saved successfully',
            'user': user
        }), 201
        
    except Exception as e:
        logger.error(f"Error in user onboarding: {str(e)}")
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<phone_number>', methods=['GET'])
def get_user(phone_number):
    """Retrieve user profile"""
    try:
        firebase_service = current_app.get_firebase_service()
        user = firebase_service.get_user(phone_number)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user}), 200
        
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return jsonify({'error': str(e)}), 500

@user_bp.route('/<phone_number>/preferences', methods=['PATCH'])
def update_user_preferences(phone_number):
    """Update user notification preferences"""
    try:
        data = request.get_json()
        
        firebase_service = current_app.get_firebase_service()
        
        # Check if user exists
        user = firebase_service.get_user(phone_number)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update preferences
        preferences = {}
        if 'push_notifications_enabled' in data:
            preferences['push_notifications_enabled'] = data['push_notifications_enabled']
        if 'email_notifications_enabled' in data:
            preferences['email_notifications_enabled'] = data['email_notifications_enabled']
        if 'dietary_restrictions' in data:
            preferences['dietary_restrictions'] = data['dietary_restrictions']
        if 'alcohol_preference' in data:
            if data['alcohol_preference'] not in ['alcoholic', 'non-alcoholic', 'no-preference']:
                return jsonify({'error': 'Invalid alcohol_preference'}), 400
            preferences['alcohol_preference'] = data['alcohol_preference']
        
        updated_user = firebase_service.update_user_preferences(phone_number, preferences)
        
        return jsonify({
            'message': 'Preferences updated successfully',
            'user': updated_user
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating user preferences: {str(e)}")
        return jsonify({'error': str(e)}), 500

