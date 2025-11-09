"""
Event Management Routes
"""
from flask import Blueprint, request, jsonify
from firebase_service import FirebaseService
from services.notification_service import NotificationService
import secrets
import logging
import requests
from services.ai_agent import AIAgentService
from langchain_integration import LangchainService
import re

logger = logging.getLogger(__name__)
event_bp = Blueprint('events', __name__)


@event_bp.route('', methods=['POST'])
def create_event():
    """Create a new event from a minimal organizer payload (lat/lon, prompt, phone)"""
    try:
        data = request.get_json()

        # Expect minimal payload: organizer_phone, latitude, longitude, prompt (natural language)
        required_fields = ['organizer_phone', 'latitude', 'longitude', 'prompt']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        firebase_service = FirebaseService()

        # Check if organizer exists
        organizer = firebase_service.get_user(data['organizer_phone'])
        if not organizer:
            return jsonify({'error': 'Organizer not found. Please complete onboarding first.'}), 404

        # Parse prompt to extract structured fields using GPT-5 via Langchain
        parsed = {}
        try:
            lc = LangchainService()
            if lc.llm:
                from datetime import datetime
                current_date = datetime.now()
                
                system = (
                    "You are an expert assistant using GPT-5 to extract structured event information from organizer prompts.\n"
                    f"Today's date is {current_date.strftime('%Y-%m-%d')}.\n"
                    "Analyze the input carefully and return a JSON object with the following keys:\n"
                    "- preferred_date: MUST be in ISO YYYY-MM-DD format. Convert any date format:\n"
                    "  * For relative dates like 'this Saturday', 'next Friday', calculate the actual date\n"
                    "  * For partial dates like '16/11', add the current year\n"
                    "  * For 'tomorrow', 'day after tomorrow', calculate from current date\n"
                    "- preferred_time_slots: array of HH:MM or HH:MM-HH:MM strings (24h format)\n"
                    "- occasion_description: concise event description\n"
                    "- expected_attendee_count: integer or null\n"
                    "- organizer_dietary: array of organizer's dietary preferences/restrictions or []\n"
                    "- cuisine_preferences: array of cuisine types mentioned or []\n\n"
                    "Location will be handled separately from coordinates - do not extract location from prompt."
                )
                
                human = (
                    "Extract structured information from this event prompt. Example output format:\n"
                    "{\n"
                    '  "preferred_date": "2025-11-16",\n'
                    '  "preferred_time_slots": ["19:00-21:00"],\n'
                    '  "occasion_description": "30th birthday dinner",\n'
                    '  "expected_attendee_count": 6,\n'
                    '  "organizer_dietary": ["vegetarian"],\n'
                    '  "cuisine_preferences": ["Asian"]\n'
                    "}\n\n"
                    f"Input prompt: {data.get('prompt')}"
                )
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": human}
                ]
                resp = lc.llm(messages)
                # Try to parse JSON from response content
                import json
                text = resp.content
                # Extract JSON block if present
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()
                elif "{" in text:
                    text = text[text.find("{"):text.rfind("}")+1]
                
                try:
                    parsed = json.loads(text)
                except Exception as e:
                    logger.error(f"Error parsing GPT-5 JSON response: {str(e)}")
        except Exception:
            parsed = {}

        # Fallback simple heuristics + regex-based parsing for robustness
        preferred_date = parsed.get('preferred_date') if parsed.get('preferred_date') else None
        preferred_time_slots = parsed.get('preferred_time_slots') if parsed.get('preferred_time_slots') else []
        occasion_description = parsed.get('occasion_description') if parsed.get('occasion_description') else None
        expected_attendee_count = parsed.get('expected_attendee_count') if parsed.get('expected_attendee_count') else None
        budget = parsed.get('budget') if parsed.get('budget') else None

        # If Langchain didn't provide structured fields, run a regex-based fallback parser
        prompt_text = (data.get('prompt') or '').strip()
        if prompt_text:
            # extract dates: ISO YYYY-MM-DD
            if not preferred_date:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", prompt_text)
                if m:
                    preferred_date = m.group(1)
                else:
                    # DD/MM/YYYY or D/M/YYYY
                    m2 = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", prompt_text)
                    if m2:
                        # normalize to YYYY-MM-DD if possible (best-effort)
                        try:
                            parts = m2.group(1).split('/')
                            d, mo, y = parts[0], parts[1], parts[2]
                            if len(y) == 2:
                                y = '20' + y
                            preferred_date = f"{y}-{int(mo):02d}-{int(d):02d}"
                        except Exception:
                            preferred_date = m2.group(1)

            # extract time slots like 18:00 or 18:00-20:00
            if not preferred_time_slots:
                times = re.findall(r"(\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?)", prompt_text)
                if times:
                    preferred_time_slots = times

            # expected attendee count e.g. '4 people' or 'for 5 guests'
            if not expected_attendee_count:
                m = re.search(r"(\d+)\s*(?:people|guests|attendees|persons)", prompt_text, re.IGNORECASE)
                if m:
                    try:
                        expected_attendee_count = int(m.group(1))
                    except Exception:
                        expected_attendee_count = None

            # budget like €30 or EUR 30 or budget 30
            if not budget:
                m = re.search(r"€\s?(\d+)|EUR\s?(\d+)|budget\s*[:~]?\s*€?(\d+)", prompt_text, re.IGNORECASE)
                if m:
                    for g in m.groups():
                        if g:
                            budget = g
                            break

            # occasion description fallback: look for keywords or else use first clause without dates/times
            if not occasion_description:
                # simple keyword-based extraction
                occasion_keywords = ['birthday', 'team', 'outing', 'dinner', 'lunch', 'meeting', 'celebration', 'anniversary']
                found_kw = None
                for kw in occasion_keywords:
                    if re.search(rf"\b{kw}\b", prompt_text, re.IGNORECASE):
                        found_kw = kw
                        break
                if found_kw:
                    occasion_description = found_kw.capitalize()
                else:
                    # strip out recognized tokens (dates, times, numbers, budget words) and take first 120 chars
                    cleaned = re.sub(r"(\d{4}-\d{2}-\d{2})|(\d{1,2}/\d{1,2}/\d{2,4})|(\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?)|€\s?\d+|EUR\s?\d+|budget[:~]?\s*\d+","", prompt_text, flags=re.IGNORECASE)
                    # Use first sentence or up to 120 chars
                    sentence = cleaned.split('\n')[0].split('.')[0].strip()
                    occasion_description = sentence[:140] if sentence else prompt_text[:140]

        # If still missing occasion_description, use a trimmed version of prompt
        if not occasion_description:
            occasion_description = (prompt_text[:140] if prompt_text else '')

        # Reverse geocode lat/lon to obtain a city/district using Nominatim
        try:
            lat = float(data.get('latitude'))
            lon = float(data.get('longitude'))
            nom_url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
            r = requests.get(nom_url, headers={'User-Agent': 'aiso-hackathon/1.0'})
            place = r.json()
            address = place.get('address', {})
            # prefer suburb, neighbourhood, city_district, town
            location_name = address.get('suburb') or address.get('neighbourhood') or address.get('city_district') or address.get('town') or address.get('city') or address.get('county')
        except Exception:
            location_name = data.get('location') or None

        # Generate unique invitation link using frontend URL
        share_token = secrets.token_urlsafe(32)
        from config import Config
        frontend_url = Config.FRONTEND_BASE_URL.rstrip('/')
        invitation_link = f"{frontend_url}/events/{share_token}/respond"

        # Create event
        event_data = {
            'organizer_phone': data['organizer_phone'],
            'organizer_email': data.get('organizer_email', organizer.get('email', '')),
            'location': location_name or data.get('location', ''),
            'occasion_description': occasion_description,
            'expected_attendee_count': expected_attendee_count,
            'preferred_date': preferred_date,
            'preferred_time_slots': preferred_time_slots,
            'invitation_link': invitation_link,
            'invitation_token': share_token,
            'organizer_prompt': data.get('prompt'),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude')
        }

        event = firebase_service.create_event(event_data)
        # If invitees were provided, send invitation messages
        invitees = data.get('invitees', [])
        invitations_summary = None
        if invitees:
            try:
                notification_service = NotificationService()
                invitations_summary = notification_service.send_event_invitations(event, invitees)
            except Exception as e:
                logger.error(f"Error sending invitations: {str(e)}")

        resp = {
            'message': 'Event created successfully',
            'event': event
        }
        if invitations_summary is not None:
            resp['invitations'] = invitations_summary

        return jsonify(resp), 201

    except Exception as e:
        logger.error(f"Error creating event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['GET'])
def get_event(event_id):
    """Retrieve event details"""
    try:
        firebase_service = FirebaseService()
        event = firebase_service.get_event(event_id)
        
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Get responses count
        responses = firebase_service.get_event_responses(event_id)
        confirmed_count = sum(1 for r in responses if r.get('attendance_confirmed'))
        
        event['response_count'] = len(responses)
        event['confirmed_attendee_count'] = confirmed_count
        
        return jsonify({'event': event}), 200
        
    except Exception as e:
        logger.error(f"Error getting event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['PATCH'])
def update_event(event_id):
    """Update event"""
    try:
        data = request.get_json()
        
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Update event
        update_data = {}
        allowed_fields = ['location', 'occasion_description', 'expected_attendee_count', 
                         'preferred_date', 'preferred_time_slots', 'status']
        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]
        
        updated_event = firebase_service.update_event(event_id, update_data)
        
        return jsonify({
            'message': 'Event updated successfully',
            'event': updated_event
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>', methods=['DELETE'])
def delete_event(event_id):
    """Cancel/delete event"""
    try:
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        # Update status to cancelled instead of deleting
        firebase_service.update_event(event_id, {'status': 'cancelled'})
        
        return jsonify({'message': 'Event cancelled successfully'}), 200
        
    except Exception as e:
        logger.error(f"Error deleting event: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/<event_id>/responses', methods=['GET'])
def get_event_responses(event_id):
    """Get all responses for an event"""
    try:
        firebase_service = FirebaseService()
        
        # Check if event exists
        event = firebase_service.get_event(event_id)
        if not event:
            return jsonify({'error': 'Event not found'}), 404
        
        responses = firebase_service.get_event_responses(event_id)
        
        return jsonify({
            'event_id': event_id,
            'responses': responses,
            'count': len(responses)
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting event responses: {str(e)}")
        return jsonify({'error': str(e)}), 500

@event_bp.route('/token/<invitation_token>', methods=['GET'])
def get_event_by_token(invitation_token):
    """Get event by invitation token"""
    try:
        firebase_service = FirebaseService()
        
        # Find event by invitation token
        events = firebase_service.db.collection('events').where('invitation_token', '==', invitation_token).stream()
        event = None
        for doc in events:
            event = doc.to_dict()
            break
        
        if not event:
            return jsonify({'error': 'Invalid invitation link'}), 404
        
        return jsonify({'event': event}), 200
        
    except Exception as e:
        logger.error(f"Error getting event by token: {str(e)}")
        return jsonify({'error': str(e)}), 500

