import os
from pathlib import Path

# アプリケーション全体で利用する設定（パス、定数など）を保持するクラス
class Config:
    # BASE_DIR: プロジェクトのルートディレクトリ (実行ファイルから2階層上)
    BASE_DIR = Path(__file__).resolve().parent.parent
    
    # 認証情報の保存ファイルパス (実行毎に認証が不要なようにTokenを保存)
    TOKEN_CACHE_FILE = BASE_DIR / "config" / "token.json"
    
    # Google API へアクセスするためのクライアント機密情報 (事前にGCPでダウンロードして配置する)
    CREDENTIALS_FILE = BASE_DIR / "config" / "credentials.json"
    
    # アプリケーションが利用する各種データを保存するディレクトリ
    DATA_DIR = BASE_DIR / "data"

    # 必須ディレクトリが存在しない場合は初期化処理で作成する
    @classmethod
    def init_dirs(cls):
        """必要なディレクトリが存在しない場合は作成する"""
        os.makedirs(cls.BASE_DIR / "config", exist_ok=True)
        os.makedirs(cls.DATA_DIR, exist_ok=True)

# モジュール読み込み時に自動でディレクトリ初期化を行う
Config.init_dirs()
