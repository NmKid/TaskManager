import sys
import os

# Add project root to path so we can import modules
sys.path.append(os.getcwd())

from src.logic.auth import GoogleAuth

def main():
    print("Starting authentication check...")
    try:
        auth = GoogleAuth()
        creds = auth.authenticate()
        if creds and creds.valid:
            print("Authentication successful!")
            print(f"Scopes: {creds.scopes}")
        else:
            print("Authentication finished but credentials are not valid.")
    except Exception as e:
        print(f"Authentication failed: {e}")

if __name__ == "__main__":
    main()
