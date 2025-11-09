"""
Restaurant Dislike/Blacklist Routes
"""
from flask import Blueprint, request, jsonify, current_app
import logging

logger = logging.getLogger(__name__)
dislike_bp = Blueprint('dislikes', __name__)

@dislike_bp.route('/<phone_number>/dislikes', methods=['POST'])
def add_dislike(phone_number):
    """Add restaurant to user's blacklist"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['restaurant_name', 'restaurant_address']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        firebase_service = current_app.get_firebase_service()
        
        # Check if user exists
        user = firebase_service.get_user(phone_number)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Validate dislike_type
        dislike_type = data.get('dislike_type', 'permanent')
        if dislike_type not in ['permanent', 'event-specific']:
            return jsonify({'error': 'dislike_type must be "permanent" or "event-specific"'}), 400
        
        # Validate reason if provided
        valid_reasons = ['poor_food', 'bad_service', 'allergy_concern', 'atmosphere', 'value', 'personal', 'other']
        reason = data.get('reason')
        if reason and reason not in valid_reasons:
            return jsonify({'error': f'reason must be one of: {", ".join(valid_reasons)}'}), 400
        
        # Create dislike
        dislike_data = {
            'user_phone': phone_number,
            'restaurant_name': data['restaurant_name'],
            'restaurant_address': data['restaurant_address'],
            'dislike_type': dislike_type,
            'event_id': data.get('event_id'),
            'reason': reason,
            'notes': data.get('notes')
        }
        
        dislike = firebase_service.add_restaurant_dislike(dislike_data)
        
        return jsonify({
            'message': 'Restaurant added to blacklist',
            'dislike': dislike
        }), 201
        
    except Exception as e:
        logger.error(f"Error adding dislike: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dislike_bp.route('/<phone_number>/dislikes', methods=['GET'])
def get_user_dislikes(phone_number):
    """Get user's blacklisted restaurants"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if user exists
        user = firebase_service.get_user(phone_number)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        dislikes = firebase_service.get_user_dislikes(phone_number)
        
        return jsonify({
            'user_phone': phone_number,
            'dislikes': dislikes,
            'count': len(dislikes)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting user dislikes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dislike_bp.route('/<phone_number>/dislikes/<dislike_id>', methods=['DELETE'])
def remove_dislike(phone_number, dislike_id):
    """Remove restaurant from blacklist (deactivate)"""
    try:
        firebase_service = current_app.get_firebase_service()
        
        # Check if user exists
        user = firebase_service.get_user(phone_number)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        firebase_service.delete_dislike(dislike_id)
        
        return jsonify({'message': 'Restaurant removed from blacklist'}), 200
        
    except Exception as e:
        logger.error(f"Error removing dislike: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dislike_bp.route('/<phone_number>/dislikes/<dislike_id>', methods=['PATCH'])
def update_dislike(phone_number, dislike_id):
    """Update dislike status"""
    try:
        data = request.get_json()
        
        firebase_service = current_app.get_firebase_service()
        
        # Check if user exists
        user = firebase_service.get_user(phone_number)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        update_data = {}
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
        if 'reason' in data:
            update_data['reason'] = data['reason']
        if 'notes' in data:
            update_data['notes'] = data['notes']
        
        updated_dislike = firebase_service.update_dislike(dislike_id, update_data)
        
        return jsonify({
            'message': 'Dislike updated successfully',
            'dislike': updated_dislike
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating dislike: {str(e)}")
        return jsonify({'error': str(e)}), 500

