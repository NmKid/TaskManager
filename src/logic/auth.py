import os
import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from config.config import Config

class GoogleAuth:
    def __init__(self):
        self.creds = None

    def authenticate(self):
        """Authenticates the user and returns credentials."""
        # 1. Load existing token if available
        if Config.TOKEN_FILE.exists():
            with open(Config.TOKEN_FILE, 'rb') as token:
                self.creds = pickle.load(token)

        # 2. Refresh or Login if needed
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not Config.CREDENTIALS_FILE.exists():
                    raise FileNotFoundError(
                        f"Credentials file not found at {Config.CREDENTIALS_FILE}. "
                        "Please download it from Google Cloud Console."
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(Config.CREDENTIALS_FILE), Config.SCOPES
                )
                self.creds = flow.run_local_server(port=0)

            # 3. Save the credentials for the next run
            Config.ensure_dirs()
            with open(Config.TOKEN_FILE, 'wb') as token:
                pickle.dump(self.creds, token)

        return self.creds

    def get_service(self, service_name, version):
        """Returns an authenticated API service resource."""
        if not self.creds:
            self.authenticate()
        return build(service_name, version, credentials=self.creds)
