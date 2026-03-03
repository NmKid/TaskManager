import json
import os
from config.config import Config

class StateManager:
    """
    ローカルのファイル (state.json) を利用して、アプリケーションの状態を管理・永続化する。
    タスクIDとイベントIDの紐付けや、過去に登録した移動イベントの履歴等を保存する役割を持つ。
    """
    def __init__(self):
        self.state_file = Config.DATA_DIR / "state.json"
        
        # 起動時に既存の状態を読み込む
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """
        ローカルJSONファイルから状態を読み込む。
        ファイルが存在しない場合は初期構造を返却する。
        """
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"状態ファイルの読み込みに失敗しました: {e}")
                # 破損している場合は初期化する
                return self._get_default_state()
        else:
            return self._get_default_state()

    def _get_default_state(self) -> dict:
        """
        状態データが未作成時の初期データを定義する。
        """
        return {
            "mapped_tasks": {}, # Task_ID: Calendar_Event_ID
            "travel_history": {} # "From_To": minutes
        }

    def _save_state(self):
        """
        現在の状態をローカルのJSONに書き込み永続化する。
        """
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"状態ファイルの書き込みに失敗しました: {e}")

    def get_event_id(self, task_id: str) -> str:
        """
        特定のタスクIDに紐づくカレンダーのイベントIDを取得する。
        """
        return self.state["mapped_tasks"].get(task_id)

    def link_task_to_event(self, task_id: str, event_id: str):
        """
        タスクがカレンダーに登録された際、そのIDの紐付けを保存する。
        """
        self.state["mapped_tasks"][task_id] = event_id
        self._save_state()

    def remove_link(self, task_id: str):
        """
        タスクのカレンダー登録が取り消された際、紐付けを解除する。
        """
        if task_id in self.state["mapped_tasks"]:
            del self.state["mapped_tasks"][task_id]
            self._save_state()

    def update_travel_history(self, location_from: str, location_to: str, minutes: int):
        """
        過去の移動時間の履歴を記録・学習する。
        """
        key = f"{location_from}_{location_to}"
        self.state["travel_history"][key] = minutes
        self._save_state()

    def get_travel_time(self, location_from: str, location_to: str) -> int:
        """
        過去の移動履歴から所要時間を取得する。履歴が無い場合は None を返す。
        """
        key = f"{location_from}_{location_to}"
        return self.state["travel_history"].get(key)
