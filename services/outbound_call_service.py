"""
Outbound Call Service - Integrates with ElevenLabs to
automatically call restaurants
"""
import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import logging
from config import Config

logger = logging.getLogger(__name__)

# Import SMS confirmation functionality
try:
    from services.sms_confirmation import (
        send_confirmation as send_sms_confirmation
    )
except ImportError:
    send_sms_confirmation = None
    logger.warning("SMS confirmation module not available")


class OutboundCallService:
    """Service for making automated calls to restaurants using ElevenLabs"""

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.agent_phone_number_id = os.getenv(
            "ELEVENLABS_PHONE_NUMBER_ID"
        )
        self.base_url = "https://api.elevenlabs.io/v1"
        use_sip_env = os.getenv("ELEVENLABS_USE_SIP", "false")
        self.use_sip = use_sip_env.lower() == "true"

        if not all([
            self.api_key, self.agent_id, self.agent_phone_number_id
        ]):
            logger.warning(
                "ElevenLabs credentials not configured. "
                "Outbound calls will be mocked."
            )

    def prepare_call_data_from_booking(
        self,
        restaurant: Dict[str, Any],
        event: Dict[str, Any],
        booking_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare call data from booking information

        Args:
            restaurant: Restaurant details from recommendations
            event: Event details
            booking_details: Booking information (party_size, date, time)

        Returns:
            Dictionary formatted for ElevenLabs API
        """
        # Format address if it's an object
        restaurant_address = restaurant.get('address', '')
        if isinstance(restaurant_address, dict):
            parts = []
            if restaurant_address.get('street'):
                parts.append(restaurant_address['street'])
            if restaurant_address.get('city'):
                parts.append(restaurant_address['city'])
            restaurant_address = (
                ', '.join(parts) if parts else 'Address not available'
            )

        # Extract dietary restrictions from event attendees
        dietary_restrictions = self._extract_dietary_restrictions(event)

        # Format dietary restrictions for the call
        diet_value = ""
        if dietary_restrictions:
            diet_value = (
                "inquire if the restaurant can accommodate these "
                f"dietary restrictions: {', '.join(dietary_restrictions)}"
            )
        else:
            diet_value = "None"

        # Get the phone number (use debug phone if enabled)
        restaurant_phone = restaurant.get('phone', '')
        if Config.USE_DEBUG_PHONE:
            restaurant_phone = Config.DEBUG_PHONE_NUMBER
            logger.info(
                f"Using debug phone number: {restaurant_phone}"
            )

        # Prepare the call data matching ElevenLabs format
        call_data = {
            "restaurant_phone": restaurant_phone,
            # Could be improved with actual name
            "customer_name": event.get('organizer_phone', 'Customer'),
            "party_size": booking_details.get(
                'party_size',
                event.get('expected_attendee_count', 2)
            ),
            "date": booking_details.get(
                'booking_date',
                event.get('preferred_date', '')
            ),
            "time": booking_details.get(
                'booking_time',
                event.get('preferred_time_slots', ['19:00'])[0]
            ),
            "diet": diet_value,
            "special_requests": booking_details.get(
                'special_requests', ''
            ),
            "restaurant_name": restaurant.get('restaurant_name', ''),
            "restaurant_address": restaurant_address
        }

        return call_data

    def _extract_dietary_restrictions(
        self, event: Dict[str, Any]
    ) -> List[str]:
        """Extract dietary restrictions from event data"""
        # This would normally pull from attendee preferences
        # For now, return empty list - you can enhance this to
        # pull from Firebase
        return []

    def make_reservation_call(
        self,
        call_data: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Make an outbound call to restaurant using ElevenLabs

        Args:
            call_data: Dictionary with call details
                (from prepare_call_data_from_booking)
            webhook_url: Optional webhook URL for call status updates

        Returns:
            Dictionary with call status and conversation_id
        """
        # Validate we have credentials
        if not all([
            self.api_key, self.agent_id, self.agent_phone_number_id
        ]):
            logger.warning(
                "⚠️  ElevenLabs credentials not configured - "
                "returning MOCK call result"
            )
            logger.info(
                f"Missing: API_KEY={bool(self.api_key)}, "
                f"AGENT_ID={bool(self.agent_id)}, "
                f"PHONE_ID={bool(self.agent_phone_number_id)}"
            )
            return self._mock_call_result(call_data)

        # Validate required fields
        required_fields = [
            'restaurant_phone', 'customer_name', 'party_size',
            'date', 'time'
        ]
        for field in required_fields:
            if field not in call_data or not call_data[field]:
                return {
                    "success": False,
                    "error": f"Missing required field: {field}",
                    "call_initiated": False
                }

        # Prepare conversation data for ElevenLabs
        conversation_data = {
            # Required dynamic variables
            "client": call_data['customer_name'],
            "date": call_data['date'],
            "time": call_data['time'],
            "diet": call_data.get('diet', 'None'),
            # Additional data
            "customer_name": call_data['customer_name'],
            "party_size": call_data['party_size'],
            "reservation_date": call_data['date'],
            "reservation_time": call_data['time'],
            "special_requests": call_data.get('special_requests', 'None')
        }

        # Choose endpoint
        if self.use_sip:
            endpoint = f"{self.base_url}/convai/sip-trunk/outbound-call"
        else:
            endpoint = f"{self.base_url}/convai/twilio/outbound-call"

        # Prepare payload
        payload = {
            "agent_id": self.agent_id,
            "agent_phone_number_id": self.agent_phone_number_id,
            "to_number": call_data['restaurant_phone'],
            "conversation_initiation_client_data": {
                "dynamic_variables": conversation_data
            }
        }

        if webhook_url:
            payload["webhook_url"] = webhook_url

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            logger.info(
                f"Initiating call to "
                f"{call_data['restaurant_phone']}"
            )
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=30
            )
            response.raise_for_status()

            call_result = response.json()

            call_sid = (
                call_result.get("callSid")
                or call_result.get("sip_call_id")
            )

            return {
                "success": True,
                "call_initiated": True,
                "conversation_id": call_result.get("conversation_id"),
                "call_sid": call_sid,
                "message": "Call initiated successfully",
                "restaurant_name": call_data.get('restaurant_name'),
                "restaurant_phone": call_data['restaurant_phone'],
                "timestamp": datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Error making outbound call: {str(e)}")
            return {
                "success": False,
                "call_initiated": False,
                "error": str(e),
                "restaurant_name": call_data.get('restaurant_name'),
                "restaurant_phone": call_data['restaurant_phone'],
                "timestamp": datetime.now().isoformat()
            }

    def _mock_call_result(
        self, call_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return a mock call result for testing when
        ElevenLabs is not configured"""
        return {
            "success": True,
            "call_initiated": True,
            "conversation_id": f"mock_{datetime.now().timestamp()}",
            "call_sid": "mock_call_sid",
            "message": (
                "Mock call initiated (ElevenLabs not configured)"
            ),
            "restaurant_name": call_data.get('restaurant_name'),
            "restaurant_phone": call_data.get('restaurant_phone'),
            "is_mock": True,
            "timestamp": datetime.now().isoformat()
        }

    def call_top_restaurants(
        self,
        recommendations: List[Dict[str, Any]],
        event: Dict[str, Any],
        booking_details: Dict[str, Any],
        max_calls: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Call top N restaurants from recommendations

        Args:
            recommendations: List of restaurant recommendations
            event: Event details
            booking_details: Booking information
            max_calls: Maximum number of restaurants to call (default: 3)

        Returns:
            List of call results
        """
        logger.info(
            f"call_top_restaurants called with "
            f"{len(recommendations)} recommendations, "
            f"max_calls={max_calls}"
        )
        results = []

        # Make sure we have valid recommendations
        if not recommendations:
            logger.warning("No recommendations provided")
            return []

        logger.info(
            f"Processing recommendations: "
            f"{json.dumps(recommendations, indent=2)}"
        )

        # Sort by rank and take top N
        recs_list = (
            recommendations if isinstance(recommendations, list)
            else recommendations.get('recommendations', [])
        )
        sorted_recs = sorted(
            recs_list,
            key=lambda x: x.get('rank', 999)
        )[:max_calls]

        logger.info(
            f"Sorted and filtered to {len(sorted_recs)} "
            f"restaurants to call"
        )

        for restaurant in sorted_recs:
            logger.info(
                f"Preparing to call restaurant rank "
                f"{restaurant.get('rank')}: "
                f"{restaurant.get('restaurant_name')}"
            )
            # Prepare call data
            call_data = self.prepare_call_data_from_booking(
                restaurant,
                event,
                booking_details
            )

            # Make the call
            logger.info(
                f"Calling {restaurant.get('restaurant_name')} at "
                f"{call_data.get('restaurant_phone')}"
            )
            result = self.make_reservation_call(call_data)
            result['rank'] = restaurant.get('rank')
            results.append(result)

            success_str = (
                '✓ Success' if result['success'] else '✗ Failed'
            )
            mock_str = ' (MOCK)' if result.get('is_mock') else ''
            logger.info(
                f"Call to {restaurant.get('restaurant_name')} "
                f"(rank {restaurant.get('rank')}): "
                f"{success_str}{mock_str}"
            )

        success_count = sum(1 for r in results if r['success'])
        logger.info(
            f"Completed calling {len(results)} restaurants. "
            f"Success: {success_count}"
        )
        return results

    def get_conversation_outcome(
        self,
        conversation_id: str,
        notification_context: Optional[Dict[str, Any]] = None,
        initiate_sms_sequence: bool = True
    ) -> Dict[str, Any]:
        """
        Get the outcome of a completed conversation

        Args:
            conversation_id: The conversation ID from
                make_reservation_call
            notification_context: Optional values (phone, date,
                time, restaurant_name, location, from_number)
                for SMS notification
            initiate_sms_sequence: When True, attempt to trigger
                the SMS workflow once a definitive conversation
                outcome is available

        Returns:
            Dictionary with conversation outcome
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "ElevenLabs not configured",
                "is_mock": True
            }

        endpoint = f"{self.base_url}/convai/conversations/{conversation_id}"
        headers = {"xi-api-key": self.api_key}

        try:
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()

            conversation_data = response.json()

            # Parse outcome from conversation
            outcome = self._parse_conversation_outcome(conversation_data)

            sms_sent = False
            sms_sid = None
            sms_error = None

            reservation_status = outcome.get("accepted")
            if initiate_sms_sequence and reservation_status is not None:
                context = self._extract_notification_context(
                    conversation_data,
                    notification_context or {}
                )
                result_tuple = self._attempt_send_sms_confirmation(
                    context,
                    reservation_confirmed=bool(reservation_status),
                    notes=outcome.get("notes")
                )
                sms_sent, sms_sid, sms_error = result_tuple
                status_label = (
                    "confirmed" if reservation_status
                    else "not confirmed"
                )
                logger.info(
                    f"[Outcome] Reservation {status_label}. "
                    f"SMS sequence initiated: "
                    f"{'yes' if sms_sent else 'no'}"
                )

            return {
                "success": True,
                "conversation_id": conversation_id,
                "reservation_accepted": outcome["accepted"],
                "confirmation_number": outcome.get(
                    "confirmation_number"
                ),
                "notes": outcome.get("notes"),
                "transcript": conversation_data.get(
                    "transcript", []
                ),
                "duration_seconds": conversation_data.get(
                    "duration_seconds"
                ),
                "sms_confirmation_sent": sms_sent,
                "sms_confirmation_sid": sms_sid,
                "sms_error": sms_error,
                "timestamp": datetime.now().isoformat()
            }

        except requests.exceptions.RequestException as e:
            logger.error(
                f"Error getting conversation outcome: {str(e)}"
            )
            return {
                "success": False,
                "error": str(e),
                "conversation_id": conversation_id,
                "sms_confirmation_sent": False,
                "timestamp": datetime.now().isoformat()
            }

    def _parse_conversation_outcome(
        self, conversation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse conversation to determine if reservation was
        accepted"""
        # Check for tool calls first
        if 'tool_calls' in conversation_data:
            for tool_call in conversation_data['tool_calls']:
                tool_name = tool_call.get('name')
                if tool_name == 'report_reservation_outcome':
                    return tool_call.get('result', {})

        # Parse transcript
        transcript = conversation_data.get('transcript', [])
        transcript_text = ' '.join([
            msg.get('text', '') for msg in transcript
        ]).lower()

        accepted = any(keyword in transcript_text for keyword in [
            'confirmed', 'booked', 'reservation confirmed', 'see you then'
        ])

        declined = any(keyword in transcript_text for keyword in [
            'no availability', 'fully booked', 'cannot accommodate', 'sorry'
        ])

        return {
            "accepted": accepted and not declined,
            "notes": "Parsed from conversation transcript",
            "confidence": "low" if not accepted and not declined else "medium"
        }

    def _extract_notification_context(
        self,
        conversation_data: Dict[str, Any],
        fallback: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Gather notification data from conversation metadata or
        provided fallback.
        Returns context needed for SMS: phone, restaurant_name,
        location, date, time, from_number
        """
        initiation = (
            conversation_data.get("conversation_initiation_client_data")
            or {}
        )
        if isinstance(initiation, dict):
            dynamic_vars = (
                initiation.get("dynamic_variables") or initiation
            )
        else:
            dynamic_vars = {}

        metadata = conversation_data.get("metadata") or {}

        phone = (
            dynamic_vars.get("customer_phone")
            or dynamic_vars.get("notification_phone")
            or metadata.get("customer_phone")
            or fallback.get("phone")
        )
        restaurant_name = (
            dynamic_vars.get("restaurant_name")
            or metadata.get("restaurant_name")
            or fallback.get("restaurant_name")
        )
        location = (
            fallback.get("location")
            or dynamic_vars.get("restaurant_location")
            or dynamic_vars.get("restaurant_address")
            or metadata.get("restaurant_location")
            or metadata.get("restaurant_address")
        )
        reservation_date = (
            fallback.get("date")
            or dynamic_vars.get("reservation_date_full")
            or metadata.get("reservation_date_full")
            or dynamic_vars.get("reservation_date")
            or dynamic_vars.get("date")
        )
        reservation_time = (
            fallback.get("time")
            or dynamic_vars.get("reservation_time")
            or dynamic_vars.get("time")
            or metadata.get("reservation_time")
        )
        from_number = (
            dynamic_vars.get("notification_from_number")
            or fallback.get("from_number")
        )

        if not all([
            phone, restaurant_name, reservation_date, reservation_time
        ]):
            logger.warning("Missing required SMS context fields")
            return None

        return {
            "phone": phone,
            "restaurant_name": restaurant_name,
            "location": location or "Location TBD",
            "date": reservation_date,
            "time": reservation_time,
            "from_number": from_number,
        }

    def _attempt_send_sms_confirmation(
        self,
        context: Optional[Dict[str, Any]],
        reservation_confirmed: bool = True,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send SMS confirmation if all required fields are present.

        Args:
            context: Dictionary with phone, restaurant_name,
                location, date, time, from_number
            reservation_confirmed: Whether the reservation was
                confirmed
            notes: Additional notes to include

        Returns:
            Tuple of (success: bool, sms_sid: Optional[str],
                error: Optional[str])
        """
        if not context:
            logger.warning(
                "Skipping SMS confirmation: "
                "insufficient reservation context."
            )
            return False, None, "Insufficient reservation context."

        if send_sms_confirmation is None:
            logger.warning(
                "Skipping SMS confirmation: "
                "sms_confirmation module is unavailable."
            )
            return False, None, "SMS confirmation module unavailable."

        try:
            sid = send_sms_confirmation(
                phone=context["phone"],
                reservation_time=context["time"],
                reservation_date=context["date"],
                restaurant_name=context["restaurant_name"],
                location=context["location"],
                from_number=context.get("from_number"),
                reservation_confirmed=reservation_confirmed,
                notes=notes,
            )
            logger.info(f"Confirmation SMS sent. Twilio SID: {sid}")
            return True, sid, None
        except Exception as exc:
            logger.error(f"Failed to send confirmation SMS: {exc}")
            return False, None, str(exc)

    def send_sms_for_reservation(
        self,
        phone: str,
        restaurant_name: str,
        location: str,
        date: str,
        reservation_time: str,
        from_number: Optional[str] = None,
        reservation_confirmed: bool = True,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send an SMS confirmation for a reservation

        Args:
            phone: Customer phone number (E.164 format)
            restaurant_name: Name of the restaurant
            location: Restaurant address/location
            date: Reservation date (YYYY-MM-DD)
            reservation_time: Reservation time
            from_number: Twilio sender number (optional)
            reservation_confirmed: Whether reservation is confirmed
            notes: Additional notes

        Returns:
            Dictionary with SMS status
        """
        context = {
            "phone": phone,
            "restaurant_name": restaurant_name,
            "location": location,
            "date": date,
            "time": reservation_time,
            "from_number": from_number or os.getenv("TWILIO_SMS_FROM")
        }

        success, sid, error = self._attempt_send_sms_confirmation(
            context,
            reservation_confirmed=reservation_confirmed,
            notes=notes
        )

        return {
            "success": success,
            "sms_sid": sid,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
