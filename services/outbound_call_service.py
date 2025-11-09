"""
Restaurant Reservation Agent using ElevenLabs Conversational AI

This script takes a JSON with reservation details, makes an outbound call to a restaurant,
and returns a JSON with the conversation outcome.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request

try:
    from sms_confirmation import (
        send_confirmation as send_sms_confirmation,
    )
except ImportError:  # pragma: no cover - optional dependency
    send_sms_confirmation = None  # type: ignore

# Load environment variables
load_dotenv()

# Initialize Flask app for webhook handling
app = Flask(__name__)


class OutboundCallService:
    """
    Agent for making restaurant reservations via phone using ElevenLabs Conversational AI
    """
    
    def __init__(self, api_key: str, agent_id: str, agent_phone_number_id: str):
        """
        Initialize the reservation agent
        
        Args:
            api_key: ElevenLabs API key
            agent_id: The ID of your configured ElevenLabs agent
            agent_phone_number_id: The phone number ID to use for outbound calls
        """
        self.api_key = api_key
        self.agent_id = agent_id
        self.agent_phone_number_id = agent_phone_number_id
        self.base_url = "https://api.elevenlabs.io/v1"
        
    @staticmethod
    def _format_agent_date(date_value: Any) -> str:
        """
        Format a reservation date for ElevenLabs by removing the year component.

        Returns an empty string if the date cannot be interpreted.
        """

        def _format_from_datetime(parsed: datetime) -> str:
            return f"{parsed.strftime('%B')} {parsed.day}"

        if not date_value:
            return ""

        if isinstance(date_value, datetime):
            return _format_from_datetime(date_value)

        if isinstance(date_value, str):
            cleaned = date_value.strip()
            if not cleaned:
                return ""

            date_formats = [
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%B %d, %Y",
                "%b %d, %Y",
            ]

            for date_format in date_formats:
                try:
                    parsed = datetime.strptime(cleaned, date_format)
                    return _format_from_datetime(parsed)
                except ValueError:
                    continue

            match = re.search(r"(.*?)(?:,\s*|\s+)\d{4}$", cleaned)
            if match:
                return match.group(1).strip()

        return str(date_value)

    def make_reservation_call(
        self,
        reservation_details: Dict[str, Any],
        use_sip: bool = False,
        webhook_url: Optional[str] = None,
        assume_confirmed: bool = False,
        wait_for_outcome: bool = True,
        outcome_timeout_seconds: float = 130.0,
        poll_interval_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Initiate an outbound call to make a restaurant reservation
        
        Args:
            reservation_details: Dictionary containing:
                - restaurant_phone: Phone number to call
                - customer_name: Name for the reservation
                - party_size: Number of people
                - date: Reservation date (YYYY-MM-DD)
                - time: Reservation time (HH:MM)
                - special_requests: Any special requests (optional)
                - restaurant_name: Restaurant name (optional, recommended)
                - restaurant_location: Restaurant location/address (optional)
                - customer_phone: Customer's phone number (optional, for SMS alerts)
            use_sip: Whether to use SIP trunk instead of Twilio
            webhook_url: Optional URL for ElevenLabs to send webhook events to
            assume_confirmed: If True, skip waiting for a conversation outcome,
                mark the reservation as accepted, and immediately trigger the SMS
                confirmation workflow using the provided reservation details.
            wait_for_outcome: When True (default), poll for the conversation outcome
                before returning. Set to False to return immediately after call initiation.
            outcome_timeout_seconds: Maximum seconds to wait for the conversation outcome.
            poll_interval_seconds: Seconds between polling attempts while awaiting the outcome.
            
        Returns:
            Dictionary containing call status and conversation details
        """
        
        # Validate input
        required_fields = ['restaurant_phone', 'customer_name', 'party_size', 'date', 'time']
        for field in required_fields:
            if field not in reservation_details:
                return {
                    "success": False,
                    "error": f"Missing required field: {field}",
                    "reservation_accepted": False
                }
        
        # Prepare the conversation initiation data
        # This data will be available to the agent during the call
        # Include both full names and short names for compatibility
        raw_diet = reservation_details.get("diet")
        if raw_diet:
            diet = (
                "inquire if the restaurant can accomodate these dietary "
                f"restrictions: {raw_diet}"
            )
        else:
            diet = ""
        original_date = reservation_details['date']
        agent_date = self._format_agent_date(original_date) or original_date

        conversation_data = {
            # Full names for internal use
            "customer_name": reservation_details['customer_name'],
            "reservation_party_size": reservation_details['party_size'],
            "reservation_date": agent_date,
            "reservation_date_full": original_date,
            "reservation_time": reservation_details['time'],
            "special_requests": reservation_details.get('special_requests', 'None'),
        }
        if diet:
            conversation_data["diet"] = diet
            conversation_data["dietaryRestrictions"] = raw_diet
        conversation_data.update({
            # Short names required by ElevenLabs as dynamic variables
            "client": reservation_details['customer_name'],
            "date": agent_date,
            "time": reservation_details['time'],
            "party_size": reservation_details['party_size'],
        })
        optional_fields = {
            "restaurant_name": reservation_details.get("restaurant_name")
            or reservation_details.get("restaurant"),
            "restaurant_location": reservation_details.get("restaurant_location")
            or reservation_details.get("restaurant_address"),
            "customer_phone": reservation_details.get("customer_phone"),
            "notification_phone": reservation_details.get("customer_phone"),
            "notification_from_number": reservation_details.get("from_number"),
        }
        for key, value in optional_fields.items():
            if value:
                conversation_data[key] = value
        
        # Choose endpoint based on telephony method
        if use_sip:
            endpoint = f"{self.base_url}/convai/sip-trunk/outbound-call"
        else:
            endpoint = f"{self.base_url}/convai/twilio/outbound-call"
        
        # Prepare request payload
        payload = {
            "agent_id": self.agent_id,
            "agent_phone_number_id": self.agent_phone_number_id,
            "to_number": reservation_details['restaurant_phone'],
            "conversation_initiation_client_data": {"dynamic_variables": conversation_data}
        }
        
        # Add webhook URL if provided
        if webhook_url:
            payload["webhook_url"] = webhook_url
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            # Make the outbound call
            response = requests.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            
            call_result = response.json()
            
            # Return initial call status
            result = {
                "success": call_result.get("success", False),
                "message": call_result.get("message", ""),
                "conversation_id": call_result.get("conversation_id"),
                "call_sid": call_result.get("callSid") or call_result.get("sip_call_id"),
                "restaurant_phone": reservation_details.get("restaurant_phone"),
                "restaurant_name": reservation_details.get("restaurant_name")
                or reservation_details.get("restaurant"),
                "restaurant_location": reservation_details.get("restaurant_location")
                or reservation_details.get("restaurant_address"),
                "reservation_details": reservation_details,
                "notification_context": {
                    "phone": reservation_details.get("customer_phone"),
                    "date": reservation_details.get("date"),
                    "time": reservation_details.get("time"),
                    "restaurant_name": reservation_details.get("restaurant_name")
                    or reservation_details.get("restaurant"),
                    "location": reservation_details.get("restaurant_location")
                    or reservation_details.get("restaurant_address"),
                    "from_number": reservation_details.get("from_number"),
                },
                "timestamp": datetime.now().isoformat(),
                "reservation_accepted": None,
            }
            print(f"RESULT ACQUIRED: {json.dumps(result, indent=2)}")
            result["reservation_accepted"] = result.get("reservation_accepted", False)
            result["assume_confirmed"] = assume_confirmed
            result["sms_confirmation_sent"] = False

            if assume_confirmed and result["success"]:
                notification_context = result.get("notification_context")
                (
                    sms_sent,
                    sms_sid,
                    sms_error,
                ) = self._attempt_send_confirmation(notification_context)
                result["reservation_accepted"] = True
                result["sms_confirmation_sent"] = sms_sent
                if sms_sid:
                    result["sms_confirmation_sid"] = sms_sid
                if sms_error:
                    result["sms_error"] = sms_error
                result["notes"] = (
                    "Reservation auto-confirmed; SMS sent immediately "
                    "via assume_confirmed flag."
                )
                print(
                    "[Auto Confirm] Reservation marked as confirmed immediately. "
                    f"SMS sent: {'yes' if sms_sent else 'no'}"
                )
            elif (
                wait_for_outcome
                and result["success"]
                and result.get("conversation_id")
            ):
                print(
                    "[Outcome] Awaiting final reservation outcome "
                    f"(timeout {outcome_timeout_seconds:.0f}s, "
                    f"interval {poll_interval_seconds:.1f}s)"
                )
                final_outcome = self._await_conversation_outcome(
                    conversation_id=result["conversation_id"],
                    notification_context=result.get("notification_context"),
                    timeout_seconds=outcome_timeout_seconds,
                    poll_interval=poll_interval_seconds,
                )

                result["awaited_outcome"] = True

                if final_outcome.get("timeout"):
                    result["success"] = False
                    result["reservation_accepted"] = None
                    result["message"] = "Timed out waiting for conversation outcome."
                    result["error"] = final_outcome.get("error")
                    result["timeout"] = True
                    print("[Outcome] Timed out waiting for the reservation outcome.")
                elif (
                    not final_outcome.get("success")
                    and final_outcome.get("reservation_accepted") is None
                ):
                    result["success"] = False
                    result["reservation_accepted"] = None
                    result["message"] = final_outcome.get(
                        "error",
                        "Failed to retrieve reservation outcome.",
                    )
                    result["error"] = final_outcome.get("error")
                    print(f"[Outcome] Failed to retrieve outcome: {result['message']}")
                else:
                    reservation_accepted = final_outcome.get("reservation_accepted")
                    result["reservation_accepted"] = reservation_accepted
                    result["success"] = bool(reservation_accepted)
                    result["message"] = (
                        "Reservation confirmed"
                        if reservation_accepted
                        else final_outcome.get("notes") or "Reservation not confirmed"
                    )
                    result["confirmation_number"] = final_outcome.get("confirmation_number")
                    result["notes"] = final_outcome.get("notes")
                    result["transcript"] = final_outcome.get("transcript")
                    result["duration_seconds"] = final_outcome.get("duration_seconds")
                    result["sms_confirmation_sent"] = final_outcome.get(
                        "sms_confirmation_sent",
                        result.get("sms_confirmation_sent", False),
                    )
                    if final_outcome.get("sms_confirmation_sid"):
                        result["sms_confirmation_sid"] = final_outcome.get(
                            "sms_confirmation_sid"
                        )
                    if final_outcome.get("sms_error"):
                        result["sms_error"] = final_outcome.get("sms_error")
                    result["outcome_timestamp"] = final_outcome.get("timestamp")

                    if reservation_accepted:
                        print("[Outcome] Reservation confirmed by agent.")
                    else:
                        print("[Outcome] Reservation was not confirmed by the agent.")
            
            # Note: The actual reservation outcome will need to be retrieved
            # after the conversation completes using the conversation_id
            print(f"Call initiated successfully. Conversation ID: {result['conversation_id']}")
            print("Use get_conversation_outcome() to retrieve the final result.")
            
            return result
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "reservation_accepted": False,
                "assume_confirmed": assume_confirmed,
                "sms_confirmation_sent": False,
                "timestamp": datetime.now().isoformat()
            }

    def make_reservations_from_list(
        self,
        reservation_details: Dict[str, Any],
        use_sip: bool = False,
        webhook_url: Optional[str] = None,
        assume_confirmed: bool = False,
        wait_for_outcome: bool = True,
        outcome_timeout_seconds: float = 130.0,
        poll_interval_seconds: float = 5.0,
    ) -> Dict[str, Any]:
        """
        Iterate through candidate restaurants until a reservation is confirmed.

        The payload can include one of these keys with a list of restaurant dicts:
        "restaurants", "restaurant_candidates", or "candidate_restaurants". Each
        restaurant entry can override values such as restaurant_name,
        restaurant_phone, restaurant_location, or special_requests.
        Other args mirror make_reservation_call.
        """
        candidate_keys = (
            "restaurants",
            "restaurant_candidates",
            "candidate_restaurants",
        )
        candidate_list: Optional[List[Dict[str, Any]]] = None
        candidate_key_used: Optional[str] = None

        for key in candidate_keys:
            value = reservation_details.get(key)
            if isinstance(value, list) and value:
                candidate_list = value
                candidate_key_used = key
                break

        if not candidate_list:
            return self.make_reservation_call(
                reservation_details,
                use_sip=use_sip,
                webhook_url=webhook_url,
                assume_confirmed=assume_confirmed,
                wait_for_outcome=wait_for_outcome,
                outcome_timeout_seconds=outcome_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )

        base_details = {
            key: value
            for key, value in reservation_details.items()
            if key not in candidate_keys
        }
        attempts: List[Dict[str, Any]] = []

        def _merge_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
            merged = {**base_details}
            merged.update(candidate or {})
            # Remove any nested candidate lists that might have been passed through.
            for candidate_key in candidate_keys:
                merged.pop(candidate_key, None)
            return merged

        def _summarize_attempts(attempt_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            summaries: List[Dict[str, Any]] = []
            for attempt in attempt_records:
                summary = dict(attempt)
                summary.pop("attempts", None)
                summaries.append(summary)
            return summaries

        for index, candidate in enumerate(candidate_list):
            merged_details = _merge_candidate(candidate)
            result = self.make_reservation_call(
                merged_details,
                use_sip=use_sip,
                webhook_url=webhook_url,
                assume_confirmed=assume_confirmed,
                wait_for_outcome=wait_for_outcome,
                outcome_timeout_seconds=outcome_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
            )
            result["attempt_index"] = index
            result["restaurant_candidate"] = candidate
            if candidate_key_used:
                result["restaurant_list_key"] = candidate_key_used
            attempts.append(result)

            reservation_confirmed = result.get("reservation_accepted")
            if isinstance(reservation_confirmed, bool) and reservation_confirmed:
                summarized_attempts = _summarize_attempts(attempts)
                response_payload = dict(result)
                response_payload["attempts"] = summarized_attempts
                response_payload["restaurant_attempts_exhausted"] = False
                return response_payload

        final_result = attempts[-1] if attempts else {
            "success": False,
            "reservation_accepted": False,
            "message": "No restaurants were attempted.",
        }

        summarized_attempts = _summarize_attempts(attempts)
        response_payload = dict(final_result)
        response_payload["attempts"] = summarized_attempts
        response_payload["restaurant_attempts_exhausted"] = True
        if not response_payload.get("reservation_accepted"):
            response_payload.setdefault(
                "message",
                "All restaurants were attempted, but the reservation was not confirmed.",
            )
            response_payload["success"] = False

        return response_payload
    
    def _await_conversation_outcome(
        self,
        conversation_id: str,
        notification_context: Optional[Dict[str, Any]],
        timeout_seconds: float,
        poll_interval: float,
    ) -> Dict[str, Any]:
        """
        Poll ElevenLabs for the conversation outcome until completion or timeout.
        """
        deadline = time.monotonic() + timeout_seconds
        last_response: Optional[Dict[str, Any]] = None

        while time.monotonic() < deadline:
            response = self.get_conversation_outcome(
                conversation_id,
                notification_context=notification_context,
                initiate_sms_sequence=False,
            )
            last_response = response

            if not response.get("success"):
                return response

            accepted = response.get("reservation_accepted")
            if accepted is not None:
                final_response = self.get_conversation_outcome(
                    conversation_id,
                    notification_context=notification_context,
                    initiate_sms_sequence=True,
                )
                reservation_status = final_response.get("reservation_accepted")
                if reservation_status is not None:
                    final_response["success"] = bool(reservation_status)
                return final_response

            time.sleep(poll_interval)

        timeout_response = last_response or {
            "success": False,
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }
        timeout_response["success"] = False
        timeout_response["error"] = "Timed out waiting for conversation outcome."
        timeout_response["timeout"] = True
        timeout_response.setdefault("reservation_accepted", None)
        return timeout_response

    def get_conversation_outcome(
        self,
        conversation_id: str,
        notification_context: Optional[Dict[str, Any]] = None,
        initiate_sms_sequence: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrieve the outcome of a completed conversation
        
        Args:
            conversation_id: The conversation ID returned from make_reservation_call
            notification_context: Optional values (phone, date, time, restaurant_name,
                location, from_number) to use when sending an automatic confirmation SMS
            initiate_sms_sequence: When True, attempt to trigger the SMS workflow once a
                definitive conversation outcome is available.
            
        Returns:
            Dictionary with conversation details and reservation outcome
        """
        
        endpoint = f"{self.base_url}/convai/conversations/{conversation_id}"
        headers = {"xi-api-key": self.api_key}
        
        try:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            
            conversation_data = response.json()
            
            # Parse the conversation to determine outcome
            # This will depend on how your agent is configured to report results
            outcome = self._parse_conversation_outcome(conversation_data)
            sms_sent = False
            sms_sid = None
            sms_error = None

            reservation_status = outcome.get("accepted")
            if (
                initiate_sms_sequence
                and reservation_status is not None
            ):
                context = self._extract_notification_context(
                    conversation_data,
                    notification_context or {},
                )
                sms_sent, sms_sid, sms_error = self._attempt_send_confirmation(
                    context,
                    reservation_confirmed=bool(reservation_status),
                    notes=outcome.get("notes"),
                )
                status_label = (
                    "confirmed"
                    if reservation_status
                    else "not confirmed"
                )
                print(
                    "[Outcome] Reservation "
                    f"{status_label}. SMS sequence initiated: "
                    f"{'yes' if sms_sent else 'no'}"
                )
            
            return {
                "success": True,
                "conversation_id": conversation_id,
                "reservation_accepted": outcome["accepted"],
                "confirmation_number": outcome.get("confirmation_number"),
                "notes": outcome.get("notes"),
                "transcript": conversation_data.get("transcript", []),
                "duration_seconds": conversation_data.get("duration_seconds"),
                "timestamp": datetime.now().isoformat(),
                "sms_confirmation_sent": sms_sent,
                "sms_confirmation_sid": sms_sid,
                "sms_error": sms_error,
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": str(e),
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
                "sms_confirmation_sent": False,
            }
    
    def _parse_conversation_outcome(self, conversation_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse conversation data to determine reservation outcome
        
        This is a simplified parser. In production, you'd want to:
        1. Configure your agent with specific tools/functions to report outcomes
        2. Use structured output from the agent
        3. Implement more sophisticated NLP parsing
        
        Args:
            conversation_data: Raw conversation data from API
            
        Returns:
            Dictionary with parsed outcome
        """

        def _normalize_bool(value: Any) -> Optional[bool]:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value != 0
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "y", "confirmed", "success"}:
                    return True
                if normalized in {
                    "false",
                    "0",
                    "no",
                    "n",
                    "declined",
                    "cancelled",
                    "failed",
                    "not confirmed",
                }:
                    return False
            return None

        def _interpret_reason(*parts: str) -> Optional[bool]:
            joined = " ".join(part for part in parts if part)
            if not joined:
                return None
            lowered = joined.lower()
            success_keywords = [
                "reservation confirmed",
                "confirmed",
                "success",
                "booked",
                "accepted",
                "secured",
            ]
            failure_keywords = [
                "not confirmed",
                "failed",
                "declined",
                "no availability",
                "unable",
                "cancelled",
                "could not confirm",
            ]
            if any(keyword in lowered for keyword in success_keywords):
                return True
            if any(keyword in lowered for keyword in failure_keywords):
                return False
            return None

        def _build_outcome(
            accepted: Optional[bool],
            notes: str,
            *,
            confidence: str = "high",
            extras: Optional[Dict[str, Any]] = None,
        ) -> Optional[Dict[str, Any]]:
            if accepted is None:
                return None
            result: Dict[str, Any] = {
                "accepted": accepted,
                "notes": notes or "Outcome reported by agent tools.",
                "confidence": confidence,
            }
            if extras:
                result.update(extras)
            return result

        def _collect_tool_results(node: Any) -> list:
            collected = []
            if isinstance(node, dict):
                if "tool_name" in node or "toolName" in node:
                    collected.append(node)
                for value in node.values():
                    collected.extend(_collect_tool_results(value))
            elif isinstance(node, list):
                for item in node:
                    collected.extend(_collect_tool_results(item))
            return collected

        # 1. Structured outcome embedded by agent tools
        if 'tool_calls' in conversation_data:
            for tool_call in conversation_data['tool_calls']:
                if tool_call.get('name') == 'report_reservation_outcome':
                    tool_result = tool_call.get('result', {}) or {}
                    accepted = _normalize_bool(
                        tool_result.get("accepted")
                        or tool_result.get("reservation_confirmed")
                        or tool_result.get("success")
                    )
                    outcome = _build_outcome(
                        accepted,
                        tool_result.get("notes")
                        or tool_result.get("reason")
                        or "Outcome reported by agent tool.",
                        extras={
                            key: value
                            for key, value in tool_result.items()
                            if key not in {"accepted", "success", "notes", "reason"}
                        },
                    )
                    if outcome:
                        return outcome

        # 2. Check for explicit conversation outcome blocks
        outcome_sources = [
            conversation_data.get("conversation_outcome"),
            conversation_data.get("metadata", {}).get("conversation_outcome")
            if isinstance(conversation_data.get("metadata"), dict)
            else None,
        ]
        for source in outcome_sources:
            if isinstance(source, dict):
                accepted = _normalize_bool(
                    source.get("reservation_confirmed")
                    or source.get("accepted")
                    or source.get("success")
                    or source.get("status")
                )
                outcome = _build_outcome(
                    accepted,
                    source.get("notes")
                    or source.get("reason")
                    or source.get("message")
                    or "Outcome reported by ElevenLabs.",
                    extras={
                        key: value
                        for key, value in source.items()
                        if key not in {"accepted", "success", "notes", "reason", "message", "status"}
                    },
                )
                if outcome:
                    return outcome

        # 3. Inspect tool results for end_call or similar signals
        aggregated_tool_results = _collect_tool_results(conversation_data)

        for tool_result in aggregated_tool_results:
            if not isinstance(tool_result, dict):
                continue
            tool_name = (
                tool_result.get("tool_name")
                or tool_result.get("toolName")
                or tool_result.get("name")
            )
            payload_candidates = []
            if "result" in tool_result:
                payload_candidates.append(tool_result["result"])
            if "result_value" in tool_result:
                raw_value = tool_result["result_value"]
                if isinstance(raw_value, str):
                    try:
                        payload_candidates.append(json.loads(raw_value))
                    except json.JSONDecodeError:
                        payload_candidates.append(raw_value)
                else:
                    payload_candidates.append(raw_value)

            for payload in payload_candidates:
                accepted = None
                notes: Optional[str] = None
                extras: Dict[str, Any] = {}

                if isinstance(payload, dict):
                    accepted = _normalize_bool(
                        payload.get("accepted")
                        or payload.get("reservation_confirmed")
                        or payload.get("success")
                        or payload.get("status")
                    )
                    notes = (
                        payload.get("message")
                        or payload.get("reason")
                        or payload.get("notes")
                        or ""
                    )
                    if accepted is None:
                        accepted = _interpret_reason(notes, payload.get("status"))
                    if accepted is None:
                        result_type_value = str(payload.get("result_type", "")).lower()
                        if result_type_value.endswith("success") or "success" in result_type_value:
                            accepted = True
                        elif any(
                            keyword in result_type_value
                            for keyword in ("fail", "decline", "reject", "unavailable")
                        ):
                            accepted = False
                    if accepted is None and tool_name == "end_call":
                        accepted = _interpret_reason(
                            payload.get("reason") or notes,
                            payload.get("status"),
                        )
                        if accepted is None:
                            status_value = payload.get("status", "").lower()
                            if status_value == "success":
                                accepted = True
                            elif status_value in {"failed", "fail", "error", "declined"}:
                                accepted = False
                            elif status_value in {"failed", "error"}:
                                accepted = False
                    extras = {
                        key: value
                        for key, value in payload.items()
                        if key
                        not in {"accepted", "success", "notes", "reason", "message", "status"}
                    }
                elif isinstance(payload, str):
                    accepted = _interpret_reason(payload)
                    notes = payload

                if accepted is None and tool_name == "end_call":
                    accepted = True
                    if not notes:
                        notes = "Reservation confirmed via end_call tool."

                outcome = _build_outcome(
                    accepted,
                    notes or "Outcome inferred from tool result.",
                    extras=extras or None,
                )
                if outcome:
                    return outcome

        # Fallback: Parse transcript for keywords
        transcript = conversation_data.get('transcript', [])
        if not transcript:
            status = (
                conversation_data.get("status")
                or conversation_data.get("state")
                or conversation_data.get("conversation_status")
                or ""
            )
            status = str(status).lower()
            if status in {"running", "in_progress", "active"}:
                notes = "Conversation still in progress."
            elif status:
                notes = f"Conversation status: {status}."
            else:
                notes = "Conversation transcript not yet available."
            return {
                "accepted": None,
                "notes": notes,
                "confidence": "unknown",
            }

        transcript_text = ' '.join([msg.get('text', '') for msg in transcript]).lower()
        
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
        fallback: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Gather notification data from conversation metadata or provided fallback.
        """
        initiation = conversation_data.get("conversation_initiation_client_data") or {}
        if isinstance(initiation, dict):
            dynamic_vars = initiation.get("dynamic_variables") or initiation
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
        )
        date = (
            fallback.get("date")
            or dynamic_vars.get("reservation_date_full")
            or metadata.get("reservation_date_full")
            or dynamic_vars.get("reservation_date")
            or dynamic_vars.get("date")
        )
        time = (
            fallback.get("time")
            or dynamic_vars.get("reservation_time")
            or dynamic_vars.get("time")
            or metadata.get("reservation_time")
        )
        from_number = (
            dynamic_vars.get("notification_from_number")
            or fallback.get("from_number")
        )

        if not all([phone, restaurant_name, date, time]):
            return None

        return {
            "phone": phone,
            "restaurant_name": restaurant_name,
            "location": location or "Location TBD",
            "date": date,
            "time": time,
            "from_number": from_number,
        }

    def _attempt_send_confirmation(
        self,
        context: Optional[Dict[str, Any]],
        *,
        reservation_confirmed: bool = True,
        notes: Optional[str] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Send SMS confirmation if all required fields are present.

        Returns:
            bool: True if the SMS was sent successfully, False otherwise.
        """
        if not context:
            print("Skipping SMS confirmation: insufficient reservation context.")
            return False, None, "Insufficient reservation context."
        if send_sms_confirmation is None:
            print(
                "Skipping SMS confirmation: sms_confirmation module is unavailable."
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
            print(f"Confirmation SMS sent. Twilio SID: {sid}")
            return True, sid, None
        except Exception as exc:  # pragma: no cover - best effort notification
            print(f"Failed to send confirmation SMS: {exc}")
            return False, None, str(exc)
    
    def load_reservation_from_json(self, json_file: str) -> Dict[str, Any]:
        """
        Load reservation details from a JSON file
        
        Args:
            json_file: Path to JSON file with reservation details
            
        Returns:
            Dictionary with reservation details
        """
        with open(json_file, 'r') as f:
            return json.load(f)
    
    def save_result_to_json(self, result: Dict[str, Any], output_file: str):
        """
        Save call result to a JSON file
        
        Args:
            result: Result dictionary from make_reservation_call or get_conversation_outcome
            output_file: Path to output JSON file
        """
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Result saved to {output_file}")


def _extract_nested_value(payload: Any, target_key: str) -> Any:
    """
    Traverse arbitrary webhook payloads to find a target key.
    """
    stack = [payload]
    seen: set[int] = set()

    while stack:
        current = stack.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)

        if isinstance(current, dict):
            if target_key in current:
                return current[target_key]
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)

    return None


def _coerce_to_bool(value: Any) -> Optional[bool]:
    """
    Convert common string/number representations to boolean.
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None

    if isinstance(value, str):
        normalized = value.strip().lower()
        truthy = {"true", "1", "yes", "y", "confirmed", "success"}
        falsy = {"false", "0", "no", "n", "declined", "cancelled"}
        if normalized in truthy:
            return True
        if normalized in falsy:
            return False

    return None


@app.route("/webhook/elevenlabs/conversation-initiation", methods=["POST"])
def elevenlabs_conversation_initiation_webhook():
    """
    Webhook endpoint to receive conversation_initiation_client_data from ElevenLabs
    when a Twilio call is initiated.
    
    This endpoint receives the webhook payload from ElevenLabs containing:
    - conversation_initiation_client_data: The data passed when initiating the call
    - Other call metadata (conversation_id, callSid, etc.)
    
    The webhook supports placeholders in the data:
    - {{client}} - Maps to customer_name
    - {{date}} - Maps to reservation_date
    - {{time}} - Maps to reservation_time
    """
    try:
        # Get webhook headers (for authentication or identification)
        webhook_headers = dict(request.headers)
        
        # Get webhook data from request
        webhook_data = request.get_json()
        
        if not webhook_data:
            return jsonify({
                "error": "No data received",
                "status": "error"
            }), 400
        
        # Extract conversation_initiation_client_data
        conversation_payload = webhook_data.get(
            "conversation_initiation_client_data", {}
        )
        if isinstance(conversation_payload, dict) and "dynamic_variables" in conversation_payload:
            conversation_data = conversation_payload.get("dynamic_variables", {}) or {}
        else:
            conversation_data = conversation_payload or {}
        
        # Extract other metadata
        conversation_id = webhook_data.get("conversation_id")
        call_sid = webhook_data.get("callSid") or webhook_data.get("call_sid")
        event_type = webhook_data.get("event_type", "conversation_initiation")
        
        # Extract or derive required dynamic variables: client, date, time
        # These are REQUIRED by ElevenLabs for the first message
        client = (
            conversation_data.get("client") or
            conversation_data.get("customer_name") or
            ""
        )
        date = (
            conversation_data.get("date") or
            conversation_data.get("reservation_date") or
            ""
        )
        time = (
            conversation_data.get("time") or
            conversation_data.get("reservation_time") or
            ""
        )
        diet_value = (
            conversation_data.get("diet") or
            conversation_data.get("dietaryRestrictions") or
            ""
        )

        # Process placeholders in the data
        # Replace {{client}}, {{date}}, {{time}} with actual values
        processed_data = {}
        for key, value in conversation_data.items():
            if isinstance(value, str):
                # Replace placeholders
                processed_value = (
                    value.replace("{{client}}", client)
                    .replace("{{date}}", date)
                    .replace("{{time}}", time)
                    .replace("{{diet}}", diet_value)
                )
                processed_data[key] = processed_value
            else:
                processed_data[key] = value
        
        # Extract reservation confirmation from ElevenLabs data collection
        reservation_confirmed_raw = _extract_nested_value(
            webhook_data,
            "reservation_confirmed",
        )
        reservation_confirmed = _coerce_to_bool(reservation_confirmed_raw)

        conversation_outcome = {
            "reservation_confirmed": reservation_confirmed,
        }
        if (
            reservation_confirmed_raw is not None
            and reservation_confirmed_raw != reservation_confirmed
        ):
            conversation_outcome["raw_value"] = reservation_confirmed_raw

        if (
            reservation_confirmed_raw is not None
            and "reservation_confirmed" not in processed_data
        ):
            processed_data["reservation_confirmed"] = reservation_confirmed_raw

        # Log the webhook data
        print("[Webhook] Received conversation initiation event")
        print(f"  Conversation ID: {conversation_id}")
        print(f"  Call SID: {call_sid}")
        print(f"  Event Type: {event_type}")
        print(f"  Headers: {json.dumps(webhook_headers, indent=2)}")
        print(f"  Client Data: {json.dumps(conversation_data, indent=2)}")
        print(f"  Processed Data: {json.dumps(processed_data, indent=2)}")
        print(f"  Conversation Outcome: {json.dumps(conversation_outcome, indent=2)}")
        
        # You can add custom processing here:
        # - Save to database
        # - Send notifications
        # - Update internal state
        # - Trigger other workflows
        
        # Return success response
        # IMPORTANT: ElevenLabs requires 'client', 'date', 'time' as top-level
        # dynamic variables in the webhook response
        return jsonify({
            # Required dynamic variables for ElevenLabs
            "client": client,
            "date": date,
            "time": time,
            "diet": diet_value,
            # Additional response data
            "status": "success",
            "message": "Webhook received successfully",
            "conversation_id": conversation_id,
            "call_sid": call_sid,
            "event_type": event_type,
            "conversation_initiation_client_data": conversation_data,
            "processed_data": processed_data,
            "reservation_confirmed": reservation_confirmed,
            "conversation_outcome": conversation_outcome,
            "timestamp": datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        print(f"[Webhook Error] {str(e)}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route("/webhook/elevenlabs/health", methods=["GET"])
def webhook_health():
    """Health check endpoint for the webhook"""
    return jsonify({
        "status": "healthy",
        "service": "ElevenLabs Webhook Handler",
        "timestamp": datetime.now().isoformat()
    }), 200


def _load_reservation_details_from_args(
    input_json: Optional[str],
    input_file: Optional[str],
) -> Dict[str, Any]:
    """
    Resolve reservation details from CLI arguments or STDIN.
    """
    if input_json and input_file:
        raise ValueError("Provide either --input-json or --input-file, not both.")

    if input_json:
        return json.loads(input_json)

    if input_file:
        with open(input_file, "r", encoding="utf-8") as f:
            return json.load(f)

    if not sys.stdin.isatty():
        stdin_payload = sys.stdin.read().strip()
        if stdin_payload:
            return json.loads(stdin_payload)

    raise ValueError(
        "No reservation details provided. "
        "Use --input-json, --input-file, or pipe JSON via STDIN."
    )


def _apply_placeholder_defaults(reservation_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure optional reservation fields exist for downstream notifications.
    """
    reservation_details.setdefault(
        "restaurant_name",
        reservation_details.get("restaurant") or "Placeholder Restaurant",
    )
    reservation_details.setdefault(
        "restaurant_location",
        reservation_details.get("restaurant_address") or "123 Placeholder Ave",
    )
    if "customer_phone" not in reservation_details:
        placeholder_phone = os.getenv("DEFAULT_CUSTOMER_PHONE", "+15555550123")
        reservation_details["customer_phone"] = placeholder_phone
    reservation_details.setdefault(
        "from_number",
        reservation_details.get("notification_from_number") or os.getenv("TWILIO_SMS_FROM"),
    )
    return reservation_details


def main():
    """
    Entry point for CLI usage.
    """

    parser = argparse.ArgumentParser(
        description="Trigger an ElevenLabs outbound reservation call from JSON input."
    )
    parser.add_argument(
        "--input-json",
        help="Raw JSON string containing reservation details.",
    )
    parser.add_argument(
        "--input-file",
        help="Path to a JSON file containing reservation details.",
    )
    parser.add_argument(
        "--output-file",
        help="Optional path to store the JSON response.",
    )
    parser.add_argument(
        "--use-sip",
        action="store_true",
        help="Use SIP trunk endpoint instead of Twilio.",
    )
    parser.add_argument(
        "--webhook-url",
        help="Optional webhook URL for ElevenLabs to send call events.",
    )
    parser.add_argument(
        "--assume-confirmed",
        action="store_true",
        help=(
            "Immediately treat the reservation as confirmed and trigger the SMS "
            "notification without waiting for the conversation outcome."
        ),
    )
    parser.add_argument(
        "--no-await-outcome",
        action="store_true",
        help=(
            "Return immediately after initiating the call without waiting for the "
            "final conversation outcome."
        ),
    )
    parser.add_argument(
        "--outcome-timeout",
        type=float,
        default=130.0,
        help=(
            "Seconds to wait for the conversation outcome before timing out. "
            "Defaults to 130 (≈2 minutes 10 seconds)."
        ),
    )
    parser.add_argument(
        "--outcome-poll-interval",
        type=float,
        default=5.0,
        help=(
            "Seconds between polling attempts while waiting for the conversation "
            "outcome. Defaults to 5."
        ),
    )
    parser.add_argument(
        "--restaurant-list-file",
        help=(
            "Path to a JSON file containing an array of restaurant objects to try "
            "sequentially if the primary restaurant cannot confirm the reservation."
        ),
    )

    args = parser.parse_args()

    # Configuration
    api_key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")
    agent_phone_number_id = os.getenv("ELEVENLABS_PHONE_NUMBER_ID")

    if not all([api_key, agent_id, agent_phone_number_id]):
        raise EnvironmentError(
            "Missing required environment variables. "
            "Set ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, and "
            "ELEVENLABS_PHONE_NUMBER_ID."
        )

    # Initialize agent
    agent = RestaurantReservationAgent(
        api_key=api_key,
        agent_id=agent_id,
        agent_phone_number_id=agent_phone_number_id,
    )

    try:
        reservation_details = _load_reservation_details_from_args(
            input_json=args.input_json,
            input_file=args.input_file,
        )
        reservation_details = _apply_placeholder_defaults(reservation_details)
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid JSON input: {exc}")
    except ValueError as exc:
        parser.error(str(exc))

    if args.restaurant_list_file:
        try:
            with open(args.restaurant_list_file, "r", encoding="utf-8") as file_handle:
                restaurant_list = json.load(file_handle)
            if not isinstance(restaurant_list, list):
                parser.error(
                    "--restaurant-list-file must contain a JSON array of restaurants."
                )
            merged_list = reservation_details.get("restaurants", [])
            if isinstance(merged_list, list):
                merged_list.extend(restaurant_list)
            else:
                merged_list = restaurant_list
            reservation_details["restaurants"] = merged_list
        except FileNotFoundError as exc:
            parser.error(f"Restaurant list file not found: {exc}")
        except json.JSONDecodeError as exc:
            parser.error(f"Invalid JSON in restaurant list file: {exc}")

    candidate_keys = ("restaurants", "restaurant_candidates", "candidate_restaurants")
    has_restaurant_list = any(
        isinstance(reservation_details.get(key), list)
        and len(reservation_details.get(key)) > 0
        for key in candidate_keys
    )

    if has_restaurant_list:
        call_result = agent.make_reservations_from_list(
            reservation_details,
            use_sip=args.use_sip,
            webhook_url=args.webhook_url,
            assume_confirmed=args.assume_confirmed,
            wait_for_outcome=not args.no_await_outcome,
            outcome_timeout_seconds=args.outcome_timeout,
            poll_interval_seconds=args.outcome_poll_interval,
        )
    else:
        call_result = agent.make_reservation_call(
            reservation_details,
            use_sip=args.use_sip,
            webhook_url=args.webhook_url,
            assume_confirmed=args.assume_confirmed,
            wait_for_outcome=not args.no_await_outcome,
            outcome_timeout_seconds=args.outcome_timeout,
            poll_interval_seconds=args.outcome_poll_interval,
        )

    if args.output_file:
        agent.save_result_to_json(call_result, args.output_file)

    json_output = json.dumps(call_result)
    print(json_output)


def run_webhook_server(port: int = 5001, host: str = "0.0.0.0"):
    """
    Run the Flask webhook server

    Args:
        port: Port to run the server on (default: 5001)
        host: Host to bind to (default: 0.0.0.0 for all interfaces)
    """
    print(f"Starting ElevenLabs webhook server on {host}:{port}")
    webhook_endpoint = (
        f"http://{host}:{port}/webhook/elevenlabs/conversation-initiation"
    )
    health_endpoint = f"http://{host}:{port}/webhook/elevenlabs/health"
    print(f"Webhook endpoint: {webhook_endpoint}")
    print(f"Health check: {health_endpoint}")
    app.run(debug=True, port=port, host=host)


if __name__ == "__main__":
    # Check if running as webhook server
    if len(sys.argv) > 1 and sys.argv[1] == "webhook":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 5001
        run_webhook_server(port=port)
    else:
        main()
