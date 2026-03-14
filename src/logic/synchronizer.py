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
        gemini_adapter: GeminiAdapter
    ):
        self.tasks = tasks_adapter
        self.calendar = calendar_adapter
        self.state = state_manager
        self.gemini = gemini_adapter

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
        print("タスクの振り分け処理を開始します...")
        
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
            print("Inbox に振り分けるべきタスクはありません。")
            return
            
        for idx, task in enumerate(tasks_in_inbox):
            title = task.get('title', '')
            notes = task.get('notes', '')
            task_id = task['id']
            
            print(f"[{idx+1}/{len(tasks_in_inbox)}] タスク '{title}' の振り分け先を分析中...")
            
            try:
                # 3. Geminiにタスクの所属リストを判定させる
                target_list_id = self._determine_target_list(title, notes, active_lists)
                
                # 4. 判定結果に基づいて移動
                if target_list_id:
                    print(f"  -> リストを移動します (Target ID: {target_list_id})")
                    # Tasks API v1 にはリスト間移動のメソッドが無いため、
                    # 先に新しいリストに同一内容で作成し、元リストから削除する擬似的な移動処理を行う
                    new_task = self.tasks.insert_task(
                        tasklist_id=target_list_id, 
                        title=title, 
                        notes=notes
                    )
                    
                    if new_task:
                         self.tasks.delete_task(tasklist_id=inbox_id, task_id=task_id)
                         print(f"  -> 移動完了")
                else:
                    print("  -> 適切な移動先が見つからなかったため、Inboxに残します。")
                    
            except Exception as e:
                print(f"  -> エラーが発生しました: {e}")
                traceback.print_exc()

        print("振り分け処理が完了しました。")

    def _determine_target_list(self, title: str, notes: str, available_lists: list) -> str:
        """
        Geminiを用いて、タスク内容と存在するリストの一覧から最適な移動先リストのIDを決定する。
        """
        # 利用可能なリストの名前とIDの辞書を作成
        list_mapping = {lst['title']: lst['id'] for lst in available_lists}
        list_names = list(list_mapping.keys())
        
        prompt = f'''
以下のタスクを、提供されたタスクリストの選択肢から最も適切なものに分類（振り分け）してください。

【タスク】
タイトル: {title}
メモ: {notes}

【選択肢となるタスクリスト】
{", ".join(list_names)}

【判断基準の例】
- 「仕事」「会議」「資料作成」など業務に関連するものは「■仕事」系統のリストへ
- 「買い物」「家事」「私用」など個人の用事は「■プライベート」系統のリストへ
- どちらにも属さない、またはリストが存在しない場合は "None" としてください。

上記の【選択肢となるタスクリスト】の名前の中から、このタスクに最も適したリストの名前を1つだけ出力してください。余計な文字列、理由や説明は一切出力しないでください。該当するものが全く無い場合は "None" と出力してください。
'''     
        try:
            # Geminiで分類実行 (リトライ付き)
            response = self.gemini.generate_content_with_retry(prompt)
            result_name = response.text.strip()
            
            # 結果が含まれているか柔軟に確認
            for name, list_id in list_mapping.items():
                if name in result_name:
                    return list_id
                    
            return None
            
        except Exception as e:
            print(f"分類推論エラー: {e}")
            return None
