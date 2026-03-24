from src.logic.tasks_adapter import TasksAdapter
from src.logic.calendar_adapter import CalendarAdapter
from src.logic.state_manager import StateManager
from src.logic.gemini_adapter import GeminiAdapter
import traceback

class Synchronizer:
    """
    タスクデータの整理と同期を行うクラス。
    最新仕様に基づき、Calendar から Tasks への同期は行わず、
    Inbox (`■メモ`) のタスクを適切な `■` リストに振り分ける処理（Organization）のみを担当する。
    """
    def __init__(
        self, 
        tasks_adapter: TasksAdapter, 
        calendar_adapter: CalendarAdapter,
        state_manager: StateManager,
        gemini_adapter: GeminiAdapter,
        logger=print
    ):
        self.tasks = tasks_adapter
        self.calendar = calendar_adapter
        self.state = state_manager
        self.gemini = gemini_adapter
        self.logger = logger

    def _get_target_lists(self) -> dict:
        """
        全タスクリストから、本ツールが処理対象とするリスト（`■`付き）を抽出する。
        Inbox (`■メモ`) や非表示作業中リスト (`■■`) を分類してディクショナリで返す。
        """
        all_lists = self.tasks.get_tasklists()
        
        target_lists = {
            "inbox": None,       # 例: ■メモ
            "active": [],        # 例: ■仕事, ■プライベート (表示対象)
            "hidden": []         # 例: ■■作業用 (非表示タスクリスト)
        }
        
        for lst in all_lists:
            title = lst.get('title', '')
            if title == '■メモ':
                target_lists["inbox"] = lst
            elif title.startswith('■■'):
                target_lists["hidden"].append(lst)
            elif title.startswith('■'):
                target_lists["active"].append(lst)
                
        return target_lists

    def organize_inbox(self):
        """
        Inbox（■メモ）に溜まっている新着タスクを分析し、最適な■リストに自動で振り分ける。
        移動先が見つからない場合は Inbox に留める。
        （※仕様上、ユーザーが手動で公式アプリにて修正可能）
        """
        self.logger("タスクの振り分け処理を開始します...")
        
        # 1. 扱うべきリスト郡を取得
        lists = self._get_target_lists()
        
        inbox = lists["inbox"]
        if not inbox:
            raise ValueError("【設定エラー】\nGoogle Tasks に「■メモ」リストが見つかりません。\n受信箱となる「■メモ」という名前のリストを作成してから、再度実行してください。")
            
        active_lists = lists["active"]
        if not active_lists:
            raise ValueError("【設定エラー】\nGoogle Tasks に振り分け先のリストが見つかりません。\n「■仕事」や「■プライベート」など、名前が「■」から始まるリストを1つ以上作成してから、再度実行してください。")

        inbox_id = inbox['id']
        
        # 2. Inboxから未完了のタスクを取得
        tasks_in_inbox = self.tasks.get_tasks(inbox_id)
        if not tasks_in_inbox:
            self.logger("Inbox に振り分けるべきタスクはありません。")
            return
            
        self.logger(f"Inboxの {len(tasks_in_inbox)} 件のタスクを一括で分析中...")
        
        try:
            # まとめてAIに判定させる
            target_list_mapping = self._determine_target_lists_batch(tasks_in_inbox, active_lists)
            
            for task in tasks_in_inbox:
                title = task.get('title', '')
                notes = task.get('notes', '')
                task_id = task['id']
                
                target_list_id = target_list_mapping.get(task_id)
                
                # 4. 判定結果に基づいて移動
                if target_list_id:
                    self.logger(f"'{title}' -> リストを移動します")
                    # Tasks API v1 にはリスト間移動のメソッドが無いため、
                    # 先に新しいリストに同一内容で作成し、元リストから削除する擬似的な移動処理を行う
                    new_task = self.tasks.insert_task(
                        tasklist_id=target_list_id, 
                        title=title, 
                        notes=notes
                    )
                    
                    if new_task:
                         self.tasks.delete_task(tasklist_id=inbox_id, task_id=task_id)
                         self.logger(f"  -> 移動完了")
                else:
                    self.logger(f"'{title}' -> 適切な移動先が見つからなかったため、Inboxに残します。")
                    
        except Exception as e:
            self.logger(f"一括分析・移動処理中にエラーが発生しました: {e}")
            import traceback
            traceback.print_exc()

        self.logger("振り分け処理が完了しました。")

    def _determine_target_lists_batch(self, tasks: list, available_lists: list) -> dict:
        """
        Geminiを用いて、複数のタスクの一括振り分け先を判定し、タスクIDと移動先リストIDの辞書を返す。
        """
        # 利用可能なリストの名前とIDの辞書を作成
        list_mapping = {lst['title']: lst['id'] for lst in available_lists}
        list_names = list(list_mapping.keys())
        
        tasks_text = ""
        for task in tasks:
            t_id = task['id']
            title = task.get('title', '')
            notes = task.get('notes', '')
            tasks_text += f"タスクID: {t_id}\nタイトル: {title}\nメモ: {notes}\n---\n"
        
        prompt = f'''
以下の複数のタスクについて、それぞれ提供されたタスクリストの選択肢から最も適切なものに分類（振り分け）してください。

【タスク一覧】
{tasks_text}

【選択肢となるタスクリスト】
{", ".join(list_names)}

【判断基準の例】
- 「仕事」「会議」「資料作成」など業務に関連するものは「■仕事」系統のリストへ
- 「買い物」「家事」「私用」など個人の用事は「■プライベート」系統のリストへ
- どちらにも属さない、またはリストが存在しない場合は "None" としてください。

出力形式は必ず以下の形式のJSONデータのみとしてください。Markdownのコードブロック(```json)は含めても構いません。
{{
  "task_id_1": "■仕事",
  "task_id_2": "None",
  ... (すべてのタスクIDについて出力)
}}
'''     
        try:
            # Geminiで分類実行 (リトライ付き)
            response = self.gemini.generate_content_with_retry(prompt)
            text = response.text
            import json
            import re
            
            # Markdownのコードブロックなどで囲まれている場合に対処
            match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
                
            result_json = json.loads(text)
            
            # リスト名をIDに変換して辞書を作成
            task_target_mapping = {}
            for t_id, list_name in result_json.items():
                list_id = list_mapping.get(list_name)
                if list_id:
                    task_target_mapping[t_id] = list_id
                    
            return task_target_mapping
            
        except Exception as e:
            self.logger(f"一括分類推論エラー: {e}")
            return {}
