# TaskManager Setup Guide

## 1. Environment Setup

```powershell
# Create Virtual Environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Install Dependencies
pip install -r requirements.txt
```

## 2. API Credentials

1.  **Google Cloud Console** でプロジェクトを作成し、以下のAPIを有効化してください。
    *   Google Tasks API
    *   Google Calendar API
2.  「OAuth 同意画面」を設定（Testing モード、User Type: External、自分のメアドを追加）。
3.  「認証情報」を作成 (OAuth 2.0 クライアント ID -> デスクトップアプリ)。
4.  JSONをダウンロードし、ファイル名を `credentials.json` に変更して、このプロジェクトの**ルートディレクトリ**に配置してください。

## 3. Gemini API Key

1.  Google AI Studio で API Key を取得。
2.  ルートディレクトリに `.env` ファイルを作成し、以下を記述してください。

```ini
GEMINI_API_KEY=your_api_key_here
```
