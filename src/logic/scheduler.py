import datetime
from typing import List, Dict, Any
from src.logic.tasks_adapter import TasksAdapter
from src.logic.calendar_adapter import CalendarAdapter
from src.logic.state_manager import StateManager
from src.logic.gemini_adapter import GeminiAdapter
import traceback

class Scheduler:
    """
    タスクを分析し、カレンダーの空き枠を見つけて登録（スケジュール化）するクラス。
    タスクの「分割処理」と「過剰分割防止（ユーザー確認の保留）」もこのクラスが担当する。
    """
    # 一度カレンダーに登録したタスクを見分ける・設定するための接頭辞
    SCHEDULED_PREFIX = "【予定済】"
    # 分割されたコンテナタスクを明示する接頭辞
    SPLIT_PREFIX = "【分割済】"
    # オーバー分割と判定する閾値
    OVER_SPLIT_THRESHOLD = 5

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
        
        # ユーザー承認待ちのタスクを保持するリスト（GUI等から後で承認・実行される）
        self.pending_split_tasks = []

    def _get_active_lists(self) -> list:
        """
        処理対象のリストのみを取得する（Inboxや非表示リストは除外）
        """
        all_lists = self.tasks.get_tasklists()
        active = []
        for lst in all_lists:
            title = lst.get('title', '')
            # ■で始まり、かつ■■やInbox（■メモ）でないものを抽出
            if title.startswith('■') and not title.startswith('■■') and title != '■メモ':
                active.append(lst)
        return active

    def schedule_tasks(self):
        """
        未スケジュールタスクを取得・分析し、カレンダーに登録する一連の処理を実行。
        """
        print("スケジューリング処理を開始します...")
        
        active_lists = self._get_active_lists()
        target_tasks = []
        
        # 1. 各リストから未完了・未スケジュールのタスクを収集
        for lst in active_lists:
            list_id = lst['id']
            # 未完了タスクのみを取得（showCompleted=Falseはデフォルト）
            tasks = self.tasks.get_tasks(list_id)
            
            for task in tasks:
                title = task.get('title', '')
                notes = task.get('notes', '')
                task_id = task['id']
                
                # ===== 予定のキャンセルの検知 (Tasks -> Cal) =====
                mapped_event_id = self.state.get_event_id(task_id)
                # 万が一過去に登録したタスクだが、手動で接頭辞やメモ欄のIDが消されている場合、
                # ユーザーが「未登録に戻した」と判定して紐付けを解除する。
                if mapped_event_id:
                     is_still_scheduled = title.startswith(self.SCHEDULED_PREFIX) or ("[Ref:EventID:" in notes)
                     if not is_still_scheduled:
                         print(f"[{title}] はユーザーにより予定が取り消されました。再登録対象とします。")
                         self.state.remove_link(task_id)
                         mapped_event_id = None # クリアして以後の処理を通す
                
                # 既に【予定済】の接頭辞があるか、メモ欄に [Ref:EventID:] の目印がある場合はスキップ
                if title.startswith(self.SCHEDULED_PREFIX) or ("[Ref:EventID:" in notes) or mapped_event_id:
                    continue
                # 既にコンテナとなっている親タスクもスキップ
                if title.startswith(self.SPLIT_PREFIX):
                    continue
                    
                target_tasks.append({
                    "list_id": list_id,
                    "task": task
                })
        
        if not target_tasks:
            print("スケジューリング対象の未登録タスクはありません。")
            return
            
        print(f"{len(target_tasks)}件のタスクをスケジューリング対象として処理します。")

        # 2. カレンダーの空き時間情報を取得 (本日から最大2週間先まで)
        now = datetime.datetime.now(datetime.timezone.utc)
        two_weeks_later = now + datetime.timedelta(days=14)
        
        freebusy_data = self.calendar.get_free_busy(time_min=now, time_max=two_weeks_later)
        print(f"Busy期間の取得数: {len(freebusy_data)}")
        
        # 3. 各タスクの処理 (分析・分割・予定登録)
        for item in target_tasks:
            list_id = item["list_id"]
            task = item["task"]
            title = task.get('title', '')
            notes = task.get('notes', '')
            task_id = task['id']
            
            print(f"---\nタスク '{title}' を処理中...")
            
            # Geminiによる詳細分析
            analysis = self.gemini.analyze_task(title, notes)
            subtasks = analysis.get("recommended_subtasks", [])
            
            # タスク分割の判定
            # threshold を超えた場合は UI側での承認待ちとしてキューに置く (今回は即時カレンダー化せず保留)
            if len(subtasks) >= self.OVER_SPLIT_THRESHOLD:
                print(f"  -> [保留] 分割数({len(subtasks)}個)が閾値(n={self.OVER_SPLIT_THRESHOLD})以上の過剰分割と判定されました。")
                print(f"  -> ユーザーの確認と承認が必要です。")
                
                # 保留リストへ格納。UIからこの配列をチェックさせる想定
                self.pending_split_tasks.append({
                    "original_task_id": task_id,
                    "list_id": list_id,
                    "title": title,
                    "notes": notes,
                    "analysis": analysis
                })
                continue
                
            elif len(subtasks) > 1:
                # 正常な範囲でのサブタスク分割実行
                print(f"  -> {len(subtasks)}個のサブタスクに分割します。")
                
                # 元タスクの名称を【分割済】に変更
                new_title = f"{self.SPLIT_PREFIX}{title}"
                task['title'] = new_title
                self.tasks.update_task(list_id, task_id, task)
                
                # 子タスクを作成（そして、この場ですぐにカレンダーを登録するか、次回のバッチに回すかは設計次第）
                # 今回は子タスクを作成して、この後の登録フローに流し込む
                for sub_title in subtasks:
                    # 子タスクをタスクリストへ登録
                    new_task_body = self.tasks.insert_task(list_id, sub_title, f"Parent: {title}")
                    if new_task_body:
                         # 子タスクのスケジュール登録 (簡易的に直接呼び出し)
                         self._schedule_single_task(list_id, new_task_body, analysis, freebusy_data)

            else:
                # 単一タスクの場合の通常スケジュール登録
                self._schedule_single_task(list_id, task, analysis, freebusy_data)

        print("スケジューリング処理が完了しました。")

    def _schedule_single_task(self, list_id: str, task: dict, analysis: dict, freebusy_data: list):
        """
        単一のタスクをカレンダーの空き時間に登録し、タスクの名称・メモを更新する内部処理。
        (空き時間の細かな探索ロジックは簡易版。要件通り移動時間なども追加可能)
        """
        title = task.get('title', '')
        notes = task.get('notes', '')
        task_id = task['id']
        duration = analysis.get("duration_minutes", 30)
        
        # NOTE: 簡易的なスケジュール登録。本来は freebusy_data と duration から
        # スケジュール可能な最も早い日時(datetime)を計算する。
        # ここでは直近（実行時）からduration分確保するダミー時間を設定（要改善）
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        print(f"  -> カレンダーへイベント登録中... (予定: {duration}分)")
        try:
             # カレンダーAPIへ登録
             event = self.calendar.insert_event(
                 summary=title, 
                 description=notes, 
                 start_time=start_time, 
                 end_time=end_time
             )
             
             event_id = event.get('id')
             
             if event_id:
                 # タスク側へ【予定済】の印とIDを付与して更新
                 new_title = f"{self.SCHEDULED_PREFIX}{title}"
                 new_notes = f"{notes}\n\n[Ref:EventID:{event_id}]"
                 task['title'] = new_title
                 task['notes'] = new_notes
                 
                 self.tasks.update_task(list_id, task_id, task)
                 self.state.link_task_to_event(task_id, event_id)
                 
                 print("  -> カレンダー登録・タスク更新が完了しました。")
                 
        except Exception as e:
             error_msg = f"タスク「{title}」のカレンダー登録時にエラーが発生しました。\nネットワーク接続や認証設定を確認してください。\n詳細: {str(e)}"
             print(f"  -> {error_msg}")
             traceback.print_exc()
             # UI側で重要なエラーとしてダイアログ表示させるため ValueError を発生させる
             raise ValueError(error_msg)
