"""
Restaurant Planner Backend - Main Flask Application
"""
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from config import Config
from firebase_service import FirebaseService
# New routes according to design document
from routes.user_routes import user_bp
from routes.event_routes import event_bp
from routes.event_response_routes import response_bp
from routes.dislike_routes import dislike_bp
from routes.ai_agent_routes import ai_agent_bp
from routes.booking_routes import booking_bp
from routes.review_routes import review_bp
from routes.outbound_call_routes import outbound_call_bp
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_firebase_service():
    """
    Get FirebaseService instance for current request (singleton per request)
    Uses Flask's g object for request-scoped service instances
    """
    if 'firebase_service' not in g:
        g.firebase_service = FirebaseService()
    return g.firebase_service

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Make service helper available to all routes
    app.get_firebase_service = get_firebase_service
    
    # Initialize Firebase connection test
    try:
        test_service = FirebaseService()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
    
    # Register blueprints according to design document
    app.register_blueprint(user_bp, url_prefix='/api/users')
    app.register_blueprint(event_bp, url_prefix='/api/events')
    app.register_blueprint(response_bp, url_prefix='/api/events')
    app.register_blueprint(dislike_bp, url_prefix='/api/users')
    app.register_blueprint(ai_agent_bp, url_prefix='/api/ai-agent')
    app.register_blueprint(booking_bp, url_prefix='/api')
    app.register_blueprint(review_bp, url_prefix='/api')
    app.register_blueprint(outbound_call_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        try:
            test_service = FirebaseService()
            firebase_connected = True
        except Exception:
            firebase_connected = False
        return jsonify({
            'status': 'healthy',
            'firebase_connected': firebase_connected
        }), 200
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

