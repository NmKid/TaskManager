from googleapiclient.discovery import build
import datetime
from src.logic.auth import GoogleAuth

class CalendarAdapter:
    """
    Google Calendar API と連携するためのアダプタクラス。
    空き時間の取得や、タスクを予定としてカレンダーに登録する処理を担当する。
    """
    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self.service = self._build_service()

    def _build_service(self):
        # 認証情報を使用して Calendar API のサービスオブジェクトを構築
        creds = self.auth.authenticate()
        return build('calendar', 'v3', credentials=creds)

    def get_free_busy(self, time_min: datetime.datetime, time_max: datetime.datetime, calendar_id: str = 'primary') -> dict:
        """
        指定した期間内の予定の入り具合 (Free/Busy 情報) を取得する。
        これにより、AIが空き時間を探してパズル的にタスクをスケジュール可能になる。
        """
        body = {
            "timeMin": time_min.isoformat() + 'Z',  # ISO8601フォーマット文字列化(UTC)
            "timeMax": time_max.isoformat() + 'Z',
            "timeZone": "Asia/Tokyo",
            "items": [{"id": calendar_id}]
        }
        
        events_result = self.service.freebusy().query(body=body).execute()
        
        # primaryカレンダーの busy 期間リストを返す
        return events_result['calendars'][calendar_id]['busy']

    def insert_event(self, summary: str, description: str, start_time: datetime.datetime, end_time: datetime.datetime, calendar_id: str = 'primary') -> dict:
        """
        カレンダーに新しい予定を登録する。
        スケジュール実行（Tasks -> Calendar）専用。
        """
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat() + '+09:00', # 日本時間
                'timeZone': 'Asia/Tokyo',
            },
            'end': {
                'dateTime': end_time.isoformat() + '+09:00',
                'timeZone': 'Asia/Tokyo',
            },
        }
        
        return self.service.events().insert(calendarId=calendar_id, body=event).execute()
