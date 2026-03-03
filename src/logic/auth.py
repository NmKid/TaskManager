import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config.config import Config

# Google Tasks と Calendar のデータを読み書きするために必要なスコープを定義
SCOPES = [
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/calendar'
]

class GoogleAuth:
    """
    Google API にアクセスするための認証を管理するクラス。
    ユーザーにブラウザでOAuth認証を求め、結果のトークンを使い回す処理を担当する。
    """
    def __init__(self):
        self.creds = None

    def authenticate(self) -> Credentials:
        """
        保存されているトークン (token.json) をロードし、有効性を確認する。
        有効なトークンが無い場合、または期限切れの場合はブラウザを開いて認証を行う。
        """
        # トークンファイルが存在する場合、ロードを試みる
        if os.path.exists(Config.TOKEN_CACHE_FILE):
            self.creds = Credentials.from_authorized_user_file(Config.TOKEN_CACHE_FILE, SCOPES)
            
        # クレデンシャルが存在しない、または無効な場合の再取得＆保存
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                # リフレッシュトークンで新しいアクセストークンを取得
                self.creds.refresh(Request())
            else:
                # ユーザーの操作（ブラウザ）を要求して新しい認証を行う
                # ※事前に client_secret_*.json を credentials.json 等にリネームして配置が必要
                flow = InstalledAppFlow.from_client_secrets_file(
                    Config.CREDENTIALS_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)
                
            # 認証後、次回の実行のためにトークンをファイルに保存
            with open(Config.TOKEN_CACHE_FILE, 'w') as token_file:
                token_file.write(self.creds.to_json())

        return self.creds
