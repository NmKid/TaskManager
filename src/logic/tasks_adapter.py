from googleapiclient.discovery import build
from src.logic.auth import GoogleAuth

class TasksAdapter:
    """
    Google Tasks API と連携するためのアダプタクラス。
    タスクリストの取得やタスクの移動・更新などをカプセル化する。
    """
    def __init__(self, auth: GoogleAuth):
        self.auth = auth
        self.service = self._build_service()

    def _build_service(self):
        # 認証情報を使用して Tasks API のサービスオブジェクトを構築
        creds = self.auth.authenticate()
        return build('tasks', 'v1', credentials=creds)

    def get_tasklists(self) -> list:
        """
        ユーザーのすべてのタスクリストを取得する。
        ■で始まるリストのみをフィルタリングする処理は上位のSynchronizerで行う。
        """
        results = self.service.tasklists().list(maxResults=100).execute()
        return results.get('items', [])

    def get_tasks(self, tasklist_id: str, show_completed=False, show_hidden=False) -> list:
        """
        指定したタスクリストIDに含まれるタスクをすべて取得する（ページネーション対応）。
        デフォルトでは完了済みのタスクや非表示タスクは除外して取得する。
        """
        tasks = []
        page_token = None
        while True:
            results = self.service.tasks().list(
                tasklist=tasklist_id, 
                showCompleted=show_completed,
                showHidden=show_hidden,
                maxResults=100,
                pageToken=page_token
            ).execute()
            tasks.extend(results.get('items', []))
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return tasks

    def insert_task(self, tasklist_id: str, title: str, notes: str = "") -> dict:
        """
        新しいタスクを指定したタスクリストに作成する。
        """
        task_body = {
            'title': title,
            'notes': notes
        }
        return self.service.tasks().insert(tasklist=tasklist_id, body=task_body).execute()

    def update_task(self, tasklist_id: str, task_id: str, task_body: dict) -> dict:
        """
        既存のタスクを更新する。（名前・メモの変更、完了状態の更新など）
        """
        return self.service.tasks().update(
            tasklist=tasklist_id, 
            task=task_id, 
            body=task_body
        ).execute()

    def move_task(self, tasklist_id: str, task_id: str, previous_id: str = None) -> dict:
        """
        タスクをリスト内で移動する（順番の変更）
        """
        return self.service.tasks().move(
            tasklist=tasklist_id, 
            task=task_id, 
            previous=previous_id
        ).execute()

    # Note: Tasks API v1 では "タスクを別のタスクリストに直接移動" (move between lists) するAPIエンドポイントは存在しません。
    # 代替手段として、新しいリストに作成して古いリストから削除する方法を用いたり、
    # あるいは手動操作を前提として上位ロジックで削除・再作成を行います。
    def delete_task(self, tasklist_id: str, task_id: str):
        """
        指定されたタスクを削除する。
        """
        return self.service.tasks().delete(
            tasklist=tasklist_id, 
            task=task_id
        ).execute()
