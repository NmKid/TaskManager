from datetime import datetime, timedelta
from googleapiclient.discovery import build
from config.config import Config
import dateutil.parser

class CalendarAdapter:
    def __init__(self, auth_service):
        self.service = auth_service.get_service('calendar', 'v3')

    def get_events(self, time_min, time_max):
        """Returns a list of events within the specified time range."""
        events_result = self.service.events().list(
            calendarId=Config.CALENDAR_ID,
            timeMin=time_min.isoformat() + 'Z',
            timeMax=time_max.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])

    def create_event(self, summary, start_time, end_time, description=None, color_id=None):
        """Creates a new calendar event."""
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Tokyo',  # Adjust as needed or make configurable
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Tokyo',
            },
        }
        if color_id:
            event['colorId'] = color_id

        return self.service.events().insert(
            calendarId=Config.CALENDAR_ID,
            body=event
        ).execute()

    def check_free_busy(self, time_min, time_max):
        """Checks free/busy status. Returns raw response."""
        body = {
            "timeMin": time_min.isoformat() + 'Z',
            "timeMax": time_max.isoformat() + 'Z',
            "timeZone": "Asia/Tokyo",
            "items": [{"id": Config.CALENDAR_ID}]
        }
        return self.service.freebusy().query(body=body).execute()
