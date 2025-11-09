"""
Calendar Service - Google Calendar Integration
"""
import logging
from datetime import datetime, timedelta
import os.path
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarService:
    """Service for Google Calendar integration"""
    
    def __init__(self):
        try:
            # Use service account credentials from the JSON file
            credentials_path = os.path.join(os.path.dirname(__file__), '..', 'firebase-credentials.json')
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path, scopes=SCOPES
            )
            self.service = build('calendar', 'v3', credentials=credentials)
            logger.info("Successfully initialized Google Calendar service")
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {str(e)}")
            self.service = None
    
    def send_calendar_invites(self, booking, attendees):
        """
        Create a public calendar event and generate sharing links
        
        Args:
            booking: Booking dictionary
            attendees: List of attendee dictionaries with email
        
        Returns:
            Dictionary with calendar event IDs and sharing link
        """
        try:
            if not self.service:
                raise Exception("Google Calendar service not initialized")

            logger.info(f"Creating calendar event for booking {booking.get('id')} with {len(attendees)} attendees")
            
            # Parse booking date and time
            booking_date = booking.get('booking_date')
            booking_time = booking.get('booking_time', '19:00')

            # Create datetime objects
            if isinstance(booking_date, dict):
                # Firestore timestamp
                start_datetime = datetime.fromtimestamp(booking_date.get('seconds', 0))
            else:
                start_datetime = datetime.fromisoformat(str(booking_date))

            # Parse time
            time_str = str(booking_time)
            if '-' in time_str:
                time_str = time_str.split('-')[0].strip()
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 and time_parts[1].isdigit() else 0

            start_datetime = start_datetime.replace(hour=hour, minute=minute)
            end_datetime = start_datetime + timedelta(hours=2)
            
            # Create event body (without attendees)
            event = {
                'summary': f"Restaurant Reservation at {booking.get('restaurant_name', 'Restaurant')}",
                'location': booking.get('restaurant_address', ''),
                'description': f"Reservation for {booking.get('party_size', 2)} guests\nRestaurant: {booking.get('restaurant_name', '')}\nAddress: {booking.get('restaurant_address', '')}",
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'UTC',
                },
                'visibility': 'public',  # Make the event public so the link can be shared
                'reminders': {
                    'useDefault': True
                },
            }
            
            # Create the event
            calendar_event_ids = []
            try:
                # Create event in the service account's calendar
                created_event = self.service.events().insert(
                    calendarId='primary',
                    body=event
                ).execute()
                
                calendar_event_ids.append(created_event['id'])
                
                # Generate a sharable Google Calendar link
                sharing_link = self.generate_google_calendar_link(booking)
                
                logger.info(f"Event created and sharing link generated")
                
                return {
                    'success': True,
                    'calendar_event_ids': calendar_event_ids,
                    'sharing_link': sharing_link
                }
                
            except HttpError as error:
                logger.error(f"Error creating calendar event: {str(error)}")
                return {
                    'success': False,
                    'error': f"Failed to create calendar event: {str(error)}"
                }
            
        except Exception as e:
            logger.error(f"Error sending calendar invites: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_ical_file(self, booking):
        """
        Generate iCal file content for a booking
        
        Args:
            booking: Booking dictionary
        
        Returns:
            iCal file content as string
        """
        try:
            # Parse booking date and time
            booking_date = booking.get('booking_date')
            booking_time = booking.get('booking_time', '19:00')

            # Create datetime objects
            if isinstance(booking_date, dict):
                # Firestore timestamp
                start_datetime = datetime.fromtimestamp(booking_date.get('seconds', 0))
            else:
                start_datetime = datetime.fromisoformat(str(booking_date))

            # Parse time robustly (support "HH:MM" and ranges like "HH:MM-HH:MM")
            time_str = str(booking_time)
            end_hour = None

            if '-' in time_str:
                # Handle time range format (e.g., "15:00-18:00")
                start_time, end_time = time_str.split('-')
                start_time = start_time.strip()
                end_time = end_time.strip()
                
                # Parse start time
                start_parts = start_time.split(':')
                hour = int(start_parts[0])
                minute = int(start_parts[1]) if len(start_parts) > 1 and start_parts[1].isdigit() else 0
                
                # Parse end time
                end_parts = end_time.split(':')
                end_hour = int(end_parts[0])
                
            else:
                # Handle single time format (e.g., "18:00" or "18")
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 and time_parts[1].isdigit() else 0


            start_datetime = start_datetime.replace(hour=hour, minute=minute)
            end_datetime = start_datetime + timedelta(hours=2)  # 2 hour duration
            
            # Format for iCal (UTC)
            start_ical = start_datetime.strftime("%Y%m%dT%H%M%SZ")
            end_ical = end_datetime.strftime("%Y%m%dT%H%M%SZ")
            created_ical = datetime.now().strftime("%Y%m%dT%H%M%SZ")
            
            # Generate iCal content
            ical_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Restaurant Planner//EN
BEGIN:VEVENT
UID:{booking.get('id', 'booking')}@restaurant-planner
DTSTAMP:{created_ical}
DTSTART:{start_ical}
DTEND:{end_ical}
SUMMARY:Restaurant Reservation at {booking.get('restaurant_name', 'Restaurant')}
DESCRIPTION:Reservation for {booking.get('party_size', 2)} guests\\nRestaurant: {booking.get('restaurant_name', '')}\\nAddress: {booking.get('restaurant_address', '')}
LOCATION:{booking.get('restaurant_address', '')}
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""
            
            return ical_content
            
        except Exception as e:
            logger.error(f"Error generating iCal file: {str(e)}")
            raise
    
    def generate_google_calendar_link(self, booking):
        """
        Generate Google Calendar link for a booking
        
        Args:
            booking: Booking dictionary
        
        Returns:
            Google Calendar URL
        """
        try:
            # Parse booking date and time
            booking_date = booking.get('booking_date')
            booking_time = booking.get('booking_time', '19:00')

            # Create datetime objects
            if isinstance(booking_date, dict):
                # Firestore timestamp
                start_datetime = datetime.fromtimestamp(booking_date.get('seconds', 0))
            else:
                start_datetime = datetime.fromisoformat(str(booking_date))

            # Parse time robustly (support "HH:MM" and ranges like "HH:MM-HH:MM")
            try:
                time_str = str(booking_time)
                if '-' in time_str:
                    # take the start time before the dash
                    time_str = time_str.split('-')[0].strip()
                time_parts = time_str.split(':')
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 and time_parts[1].isdigit() else 0
            except Exception:
                logger.warning(f"Unable to parse booking_time '{booking_time}', defaulting to 19:00")
                hour, minute = 19, 0

            start_datetime = start_datetime.replace(hour=hour, minute=minute)
            end_datetime = start_datetime + timedelta(hours=2)  # 2 hour duration
            
            # Format for Google Calendar URL
            start_google = start_datetime.strftime("%Y%m%dT%H%M%SZ")
            end_google = end_datetime.strftime("%Y%m%dT%H%M%SZ")
            
            # Build Google Calendar URL
            title = f"Restaurant Reservation at {booking.get('restaurant_name', 'Restaurant')}"
            details = f"Reservation for {booking.get('party_size', 2)} guests\\nRestaurant: {booking.get('restaurant_name', '')}\\nAddress: {booking.get('restaurant_address', '')}"
            location = booking.get('restaurant_address', '')
            
            google_cal_url = (
                f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                f"&text={title.replace(' ', '+')}"
                f"&dates={start_google}/{end_google}"
                f"&details={details.replace(' ', '+').replace('\\n', '%0A')}"
                f"&location={location.replace(' ', '+')}"
            )
            
            return google_cal_url
            
        except Exception as e:
            logger.error(f"Error generating Google Calendar link: {str(e)}")
            raise

