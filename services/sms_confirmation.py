"""Send SMS confirmation messages for restaurant bookings via Twilio."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from twilio.base.exceptions import TwilioRestException  # type: ignore
from twilio.rest import Client  # type: ignore

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send an SMS reservation confirmation via Twilio."
    )
    parser.add_argument(
        "--phone",
        required=True,
        help="Recipient phone number in E.164 format, e.g. +15555551234.",
    )
    parser.add_argument(
        "--time",
        required=True,
        help="Reservation time, e.g. 7:30 PM",
    )
    parser.add_argument(
        "--date",
        required=True,
        help="Reservation date, e.g. 2025-11-09",
    )
    parser.add_argument(
        "--restaurant",
        required=True,
        help="Restaurant name.",
    )
    parser.add_argument(
        "--location",
        required=True,
        help="Restaurant location or address.",
    )
    parser.add_argument(
        "--from-number",
        default=os.getenv("TWILIO_SMS_FROM"),
        help=(
            "Twilio SMS-enabled sender number "
            "(defaults to TWILIO_SMS_FROM env var)."
        ),
    )
    return parser.parse_args()


def format_phone_number(number: str) -> str:
    number = number.strip()
    if not number:
        raise ValueError("Phone number must not be empty.")
    if not number.startswith("+"):
        raise ValueError(
            "Phone numbers must be provided in E.164 format (start with '+')."
        )
    return number


def parse_reservation_datetime(
    date_str: str,
    time_str: str,
    duration_minutes: int = 120,
) -> tuple[dt.datetime, dt.datetime]:
    try:
        reservation_date = dt.datetime.strptime(
            date_str.strip(),
            "%Y-%m-%d",
        ).date()
    except ValueError as exc:
        raise ValueError(
            "Date must be provided in ISO format YYYY-MM-DD."
        ) from exc

    time_formats = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I %p")
    reservation_time = None
    for time_format in time_formats:
        try:
            reservation_time = dt.datetime.strptime(
                time_str.strip(),
                time_format,
            ).time()
            break
        except ValueError:
            continue
    if reservation_time is None:
        raise ValueError(
            "Time must be provided in formats such as '19:30', '19:30:00', "
            "'7:30 PM', or '7 PM'."
        )

    start = dt.datetime.combine(reservation_date, reservation_time)
    end = start + dt.timedelta(minutes=duration_minutes)
    return start, end


def format_display_date(date_obj: dt.date) -> str:
    """Return a human-friendly date string without the year component."""
    month_name = date_obj.strftime("%B")
    day = date_obj.day
    return f"{month_name} {day}"


def build_calendar_link(
    restaurant: str,
    location: str,
    start: dt.datetime,
    end: dt.datetime,
) -> str:
    time_format = "%Y%m%dT%H%M%S"
    params = {
        "action": "TEMPLATE",
        "text": restaurant,
        "dates": f"{start.strftime(time_format)}/{end.strftime(time_format)}",
        "details": f"Reservation at {restaurant}",
        "location": location,
    }
    base_url = "https://calendar.google.com/calendar/render?"
    return base_url + urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote,
    )


def shorten_url(url: str) -> str:
    request_url = (
        "https://tinyurl.com/api-create.php?"
        + urllib.parse.urlencode({"url": url})
    )
    try:
        with urllib.request.urlopen(request_url, timeout=5) as response:
            shortened = response.read().decode("utf-8").strip()
            if shortened:
                return shortened
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass
    return url


def build_message_body(
    restaurant: str,
    date: str,
    time: str,
    location: str,
    reservation_confirmed: bool = True,
    notes: str | None = None,
) -> str:
    start, end = parse_reservation_datetime(date, time)
    display_date = format_display_date(start.date())
    schedule = f"When: {display_date} at {time}"
    location_line = f"Where: {location}"

    if reservation_confirmed:
        calendar_link = build_calendar_link(restaurant, location, start, end)
        short_calendar_link = shorten_url(calendar_link)
        message = (
            f"Great news! Your Reserv-booking at {restaurant} is confirmed!\n"
            f"{schedule}\n"
            f"{location_line}\n\n"
            f"Ready to go? Add it to your calendar: {short_calendar_link}\n\n"
        )
    else:
        message = (
            f"We weren't able to confirm your reservation at {restaurant} yet.\n"
            f"{schedule}\n"
            f"{location_line}\n"
        )
        message += (
            "\nWe'll keep you posted if anything changes. "
        )

    return message


def send_confirmation(
    phone: str,
    reservation_time: str,
    reservation_date: str,
    restaurant_name: str,
    location: str,
    from_number: str | None,
    reservation_confirmed: bool = True,
    notes: str | None = None,
) -> str:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")

    if not account_sid:
        raise RuntimeError(
            "Set TWILIO_ACCOUNT_SID in the environment before sending."
        )
    if not auth_token:
        raise RuntimeError(
            "Set TWILIO_AUTH_TOKEN in the environment before sending."
        )

    raw_sender = (
        from_number
        or os.getenv("TWILIO_SMS_FROM")
        or os.getenv("TWILIO_DEFAULT_SMS_FROM")
    )
    if not raw_sender:
        raise RuntimeError(
            "Provide --from-number or set TWILIO_SMS_FROM "
            "or TWILIO_DEFAULT_SMS_FROM."
        )

    sender = format_phone_number(raw_sender)
    recipient = format_phone_number(phone)

    client = Client(account_sid, auth_token)
    body = build_message_body(
        restaurant_name,
        reservation_date,
        reservation_time,
        location,
        reservation_confirmed=reservation_confirmed,
        notes=notes,
    )

    message = client.messages.create(
        body=body,
        from_=sender,
        to=recipient,
    )
    return message.sid


def main() -> None:
    if load_dotenv:
        load_dotenv()

    args = parse_args()
    try:
        sid = send_confirmation(
            phone=args.phone,
            reservation_time=args.time,
            reservation_date=args.date,
            restaurant_name=args.restaurant,
            location=args.location,
            from_number=args.from_number,
        )
    except (RuntimeError, ValueError, TwilioRestException) as exc:
        sys.stderr.write(f"Failed to send confirmation: {exc}\n")
        sys.exit(1)

    print(f"Sent confirmation message. SID: {sid}")


if __name__ == "__main__":
    main()
