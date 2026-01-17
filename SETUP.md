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
(設定済み) `config/config.py` に直接記述されています。

## 4. 実行手順 (Next Steps)

1.  ダウンロードした `credentials.json` をこのフォルダ (`c:\Antigravity\TaskManager\`) に配置してください。
2.  以下のコマンドでアプリを起動します。
    ```powershell
    python src/main.py
    ```
3.  初回はブラウザが開き、Google認証が求められます。許可してください。
4.  アプリが起動したら、「振り分け」「同期」「スケジュール実行」の順にボタンを押して動作を確認してください。
