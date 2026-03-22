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
        # timeMin, timeMax は datetime オブジェクト。そのまま isoformat() に 'Z' を付けると
        # tzinfo がある場合に +09:00Z のような不正なフォーマットになることがあるため、
        # 確実にUTCに変換してからフォーマットするか、そのまま isoformat() を渡す。
        # Google API は '2023-01-01T00:00:00+09:00' のような形式を好む。
        t_min_str = time_min.isoformat()
        if not time_min.tzinfo:
            t_min_str += 'Z'
            
        t_max_str = time_max.isoformat()
        if not time_max.tzinfo:
            t_max_str += 'Z'

        body = {
            "timeMin": t_min_str,
            "timeMax": t_max_str,
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
        start_str = start_time.isoformat()
        if not start_time.tzinfo:
            start_str += '+09:00'
            
        end_str = end_time.isoformat()
        if not end_time.tzinfo:
            end_str += '+09:00'

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_str,
                'timeZone': 'Asia/Tokyo',
            },
            'end': {
                'dateTime': end_str,
                'timeZone': 'Asia/Tokyo',
            },
        }
        
        return self.service.events().insert(calendarId=calendar_id, body=event).execute()
