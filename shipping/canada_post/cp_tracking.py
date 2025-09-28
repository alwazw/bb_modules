import os
import sys
import requests
import base64
import xml.etree.ElementTree as ET

# --- Project Path Setup ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from common.utils import get_canada_post_credentials
from database.db_utils import log_api_call

# --- Constants ---
CP_API_TRACKING_URL_BASE = "https://soa-gw.canadapost.ca/vis/track/pin/"

def get_tracking_details(conn, cp_creds, tracking_pin):
    """
    Fetches the detailed tracking history for a given tracking PIN from the Canada Post API.

    Args:
        conn: Active database connection for logging.
        cp_creds (dict): Canada Post API credentials.
        tracking_pin (str): The tracking PIN of the shipment.

    Returns:
        list: A list of dictionaries, where each dictionary represents a tracking event.
              Returns an empty list if the API call fails or no events are found.
    """
    print(f"INFO: Fetching tracking details for PIN: {tracking_pin}...")
    if not tracking_pin:
        print("ERROR: Tracking PIN is null or empty.")
        return []

    url = f"{CP_API_TRACKING_URL_BASE}{tracking_pin}/detail"
    auth_string = f"{cp_creds[0]}:{cp_creds[1]}"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')

    headers = {
        'Accept': 'application/vnd.cpc.track-v2+xml',
        'Authorization': f'Basic {auth_b64}',
        'Accept-language': 'en-CA'
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        is_success = 200 <= response.status_code < 300

        log_api_call(
            conn, 'CanadaPost', 'GetTrackingDetails', tracking_pin,
            request_payload={'url': url},
            response_body=response.text,
            status_code=response.status_code,
            is_success=is_success
        )

        if not is_success:
            print(f"ERROR: Received HTTP {response.status_code} from CP tracking API for PIN {tracking_pin}.")
            return []

        # Parse the XML response
        root = ET.fromstring(response.text)
        ns = {'cp': 'http://www.canadapost.ca/ws/track'}
        tracking_events = []

        for event in root.findall('cp:significant-events/cp:occurrence', ns):
            event_data = {
                'code': event.find('cp:event-identifier', ns).text,
                'description': event.find('cp:event-description', ns).text,
                'date': event.find('cp:event-date', ns).text,
                'time': event.find('cp:event-time', ns).text,
                'signatory': event.find('cp:signatory-name', ns).text if event.find('cp:signatory-name', ns) is not None else ''
            }
            tracking_events.append(event_data)

        if not tracking_events:
            print(f"INFO: No significant tracking events found for PIN {tracking_pin}.")
        else:
            print(f"SUCCESS: Found {len(tracking_events)} tracking events for PIN {tracking_pin}.")

        return tracking_events

    except requests.exceptions.RequestException as e:
        print(f"ERROR: Network error while fetching tracking details for PIN {tracking_pin}: {e}")
        log_api_call(
            conn, 'CanadaPost', 'GetTrackingDetails', tracking_pin,
            request_payload={'url': url},
            response_body=str(e),
            status_code=500,
            is_success=False
        )
        return []
    except (ET.ParseError, AttributeError) as e:
        print(f"ERROR: Could not parse XML response for PIN {tracking_pin}. Error: {e}")
        return []