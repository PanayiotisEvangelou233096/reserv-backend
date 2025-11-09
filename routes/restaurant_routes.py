"""
Restaurant Routes
"""
from flask import Blueprint, jsonify, current_app

restaurant_bp = Blueprint('restaurants', __name__)

@restaurant_bp.route('', methods=['GET'])
def get_restaurants():
    """Get all restaurants from Firestore"""
    try:
        firebase_service = current_app.get_firebase_service()
        restaurants = []
        
        # Get all restaurants from Firestore
        for doc in firebase_service.db.collection('restaurants').stream():
            restaurant = doc.to_dict()
            restaurants.append({
                'id': doc.id,
                'name': restaurant.get('name', ''),
                'cuisine': restaurant.get('cuisine', []),
                'address': restaurant.get('address_obj', {}),
                'price_level': restaurant.get('price_level', ''),
                'price_range': restaurant.get('price_range', {}),
                'rating': restaurant.get('rating', 0.0),
                'num_reviews': restaurant.get('num_reviews', 0),
                'description': restaurant.get('description', ''),
                'website': restaurant.get('website', ''),
                'phone': restaurant.get('phone', ''),
                'hours': restaurant.get('hours', {}),
                'latitude': restaurant.get('latitude', 0.0),
                'longitude': restaurant.get('longitude', 0.0)
            })
        
        return jsonify({
            'restaurants': restaurants,
            'count': len(restaurants)
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500