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
        gemini_adapter: GeminiAdapter,
        logger=print
    ):
        self.tasks = tasks_adapter
        self.calendar = calendar_adapter
        self.state = state_manager
        self.gemini = gemini_adapter
        self.log = logger
        
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

    def schedule_tasks(self, work_start_hour: int = 6, work_end_hour: int = 22):
        """
        未スケジュールタスクを取得・分析し、カレンダーに登録する一連の処理を実行。
        """
        self.log("スケジューリング処理を開始します...")
        
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
                         self.log(f"[{title}] はユーザーにより予定が取り消されました。再登録対象とします。")
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
            self.log("スケジューリング対象の未登録タスクはありません。")
            return
            
        self.log(f"{len(target_tasks)}件のタスクをスケジューリング対象として処理します。")

        # 2. カレンダーの空き時間情報を取得 (本日から最大2週間先まで)
        now = datetime.datetime.now(datetime.timezone.utc)
        two_weeks_later = now + datetime.timedelta(days=14)
        
        freebusy_data = self.calendar.get_free_busy(time_min=now, time_max=two_weeks_later)
        self.log(f"APIからのBusy期間の取得数: {len(freebusy_data)}")
        
        # --- 架空のBusy（時間外ブロック）を注入 ---
        # 1日のうち、終了時間(work_end_hour) 〜 翌日の開始時間(work_start_hour) をBusyとして扱う
        # ※JSTタイムゾーンを前提とする（UIで指定される時間が日本時間であるため）
        jst_tz = datetime.timezone(datetime.timedelta(hours=9))
        now_jst = now.astimezone(jst_tz)
        base_date = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for i in range(16): # 余裕を持って前後1日含む16日分生成
            current_day = base_date + datetime.timedelta(days=i-1)
            
            # ブロック開始: その日の end_hour
            block_start = current_day.replace(hour=work_end_hour)
            # ブロック終了: 翌日の start_hour
            block_end = current_day + datetime.timedelta(days=1)
            block_end = block_end.replace(hour=work_start_hour)
            
            # UTCのISOフォーマット文字列で injection
            freebusy_data.append({
                'start': block_start.astimezone(datetime.timezone.utc).isoformat(),
                'end': block_end.astimezone(datetime.timezone.utc).isoformat()
            })
            
        self.log(f"※時間外ブロックを注入しました（現在の総Busyブロック数={len(freebusy_data)}）")
        
        # 検索開始時間を直近の15分単位の時刻にする(UTC)
        search_start = now
        remainder = search_start.minute % 15
        search_start += datetime.timedelta(minutes=15 - remainder, seconds=-search_start.second, microseconds=-search_start.microsecond)

        # 3. 各タスクの処理 (分析・分割・予定登録)
        for item in target_tasks:
            list_id = item["list_id"]
            task = item["task"]
            title = task.get('title', '')
            notes = task.get('notes', '')
            task_id = task['id']
            
            # 明示的な時間指定のパース (末尾の [:：][数値][HhMmＨｈＭｍ])
            import re
            match = re.search(r'[:：]\s*([0-9０-９]+)\s*([HhMmＨｈＭｍ])\s*$', title)
            explicit_duration = None
            if match:
                num_str = match.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789'))
                unit_str = match.group(2).lower().translate(str.maketrans('ｈｍ', 'hm'))
                val = int(num_str)
                explicit_duration = val * 60 if unit_str == 'h' else val
                
                # タイトルから時間指定部分を削除し、本体も更新しておく
                title = title[:match.start()].strip()
                task['title'] = title
            
            self.log(f"---\nタスク '{title}' を処理中...")
            if explicit_duration:
                self.log(f"  -> 明示的な所要時間の指定を検出しました: {explicit_duration}分")
            
            # Geminiによる詳細分析
            analysis = self.gemini.analyze_task(title, notes)
            
            # 明示的な時間指定があれば優先して適用し、AIによる勝手なタスク分割を抑制する
            if explicit_duration is not None:
                analysis["duration_minutes"] = explicit_duration
                analysis["recommended_subtasks"] = []
                
            subtasks = analysis.get("recommended_subtasks", [])
            
            # タスク分割の判定
            # threshold を超えた場合は UI側での承認待ちとしてキューに置く (今回は即時カレンダー化せず保留)
            if len(subtasks) >= self.OVER_SPLIT_THRESHOLD:
                self.log(f"  -> [保留] 分割数({len(subtasks)}個)が閾値(n={self.OVER_SPLIT_THRESHOLD})以上の過剰分割と判定されました。")
                self.log(f"  -> ユーザーの確認と承認が必要です。")
                
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
                self.log(f"  -> {len(subtasks)}個のサブタスクに分割します。")
                
                # 元タスクの名称を【分割済】に変更
                new_title = f"{self.SPLIT_PREFIX}{title}"
                task['title'] = new_title
                self.tasks.update_task(list_id, task_id, task)
                
                # 子タスクを作成
                for sub_title in subtasks:
                    # 子タスクをタスクリストへ登録
                    new_task_body = self.tasks.insert_task(list_id, sub_title, f"Parent: {title}")
                    if new_task_body:
                         # 子タスクのスケジュール登録
                         search_start = self._schedule_single_task(list_id, new_task_body, analysis, freebusy_data, search_start)

            else:
                # 単一タスクの場合の通常スケジュール登録
                search_start = self._schedule_single_task(list_id, task, analysis, freebusy_data, search_start)

        self.log("スケジューリング処理が完了しました。")

    def _schedule_single_task(self, list_id: str, task: dict, analysis: dict, freebusy_data: list, search_start: datetime.datetime):
        """
        単一のタスクをカレンダーの空き時間に登録し、タスクの名称・メモを更新する内部処理。
        """
        title = task.get('title', '')
        notes = task.get('notes', '')
        task_id = task['id']
        # 15分単位にするため不足分を切り上げる（最低15分）
        base_dur = analysis.get("duration_minutes", 30)
        rem = base_dur % 15
        duration = base_dur if rem == 0 else base_dur + (15 - rem)
        
        # ISO形式の文字列をdatetime(UTC)に変換するヘルパー
        def parse_iso(ts_str):
            # Google APIの '2023-01-01T10:00:00Z' や '+09:00' に対応
            ts_str = ts_str.replace('Z', '+00:00')
            return datetime.datetime.fromisoformat(ts_str)
            
        # -----------------------------
        # 空き時間 (free space) 探索ロジック
        # -----------------------------
        candidate_start = search_start
        while True:
            candidate_end = candidate_start + datetime.timedelta(minutes=duration)
            conflict = False
            
            for busy in freebusy_data:
                b_start = parse_iso(busy['start'])
                b_end = parse_iso(busy['end'])
                
                # 候補時間がbusy期間に被っているか検出
                latest_start = max(candidate_start, b_start)
                earliest_end = min(candidate_end, b_end)
                
                if latest_start < earliest_end:  # overlap exists
                    conflict = True
                    # 候補をbusyの終了時刻まで移動させる
                    candidate_start = b_end
                    # 新しいcandidate_startを15分スナップに乗せる
                    rem = candidate_start.minute % 15
                    if rem != 0 or candidate_start.second != 0 or candidate_start.microsecond != 0:
                        candidate_start += datetime.timedelta(minutes=15 - rem, seconds=-candidate_start.second, microseconds=-candidate_start.microsecond)
                    break
            
            if not conflict:
                # オーバーラップするbusy期間がなければ、ここを空き時間として決定
                start_time = candidate_start
                end_time = candidate_end
                break

        # 日本時間(JST)でログ出力するためのフォーマット
        jst_tz = datetime.timezone(datetime.timedelta(hours=9))
        start_jst = start_time.astimezone(jst_tz)
        end_jst = end_time.astimezone(jst_tz)
        
        self.log(f"  -> 「{title}」をカレンダーへイベント登録中... [{start_jst.strftime('%H:%M')} - {end_jst.strftime('%H:%M')} , 予定: {duration}分]")
        try:
             # カレンダーAPIへ登録
             event = self.calendar.insert_event(
                 summary=f"◆{title}", # 仕様変更：カレンダー側の予定タイトル先頭に◆を付与
                 description=notes, 
                 start_time=start_time, 
                 end_time=end_time
             )
             
             event_id = event.get('id')
             
             if event_id:
                 # メモリ上のbusyリストに今回の登録分を追加し、直後のタスクが被らないようにする
                 freebusy_data.append({
                     'start': event['start'].get('dateTime', event['start'].get('date')),
                     'end': event['end'].get('dateTime', event['end'].get('date'))
                 })
                 
                 # タスク側へ【予定済】の印とIDを付与して更新
                 new_title = f"{self.SCHEDULED_PREFIX}{title}"
                 new_notes = f"{notes}\n\n[Ref:EventID:{event_id}]"
                 task['title'] = new_title
                 task['notes'] = new_notes
                 
                 self.tasks.update_task(list_id, task_id, task)
                 self.state.link_task_to_event(task_id, event_id)
                 
                 self.log(f"  -> {title} のカレンダー登録・タスク更新が完了しました。")
                 
        except Exception as e:
             error_msg = f"タスク「{title}」のカレンダー登録時にエラーが発生しました。\nネットワーク接続や認証設定を確認してください。\n詳細: {str(e)}"
             self.log(f"  -> {error_msg}")
             traceback.print_exc()
             # UI側で重要なエラーとしてダイアログ表示させるため ValueError を発生させる
             raise ValueError(error_msg)
             
        # 次の検索開始時間をこのタスクの終了直後として返す
        return end_time

    def undo_scheduled_tasks(self):
        """
        （テスト用機能）
        「【予定済】」となっているタスクから接頭辞とメモ欄のEventID表記を削除し、
        タスク側のみを未スケジュールの状態に復元する。
        ※ カレンダーの予定自体はこの処理では削除されません。
        """
        import re
        self.log("元に戻す(Undo) 処理を開始します...")
        
        all_lists = self.tasks.get_tasklists()
        undo_count = 0
        
        for lst in all_lists:
            list_id = lst['id']
            # すべてのタスクを取得（完了済み等も必要に応じて含む場合は show_completed=True 等を要検討だが今回はデフォルト）
            tasks = self.tasks.get_tasks(list_id)
            
            for task in tasks:
                title = task.get('title', '')
                notes = task.get('notes', '')
                task_id = task['id']
                
                is_scheduled_title = title.startswith(self.SCHEDULED_PREFIX)
                has_event_id_note = "[Ref:EventID:" in notes
                
                if is_scheduled_title or has_event_id_note:
                    self.log(f"  -> 対象タスク発見: {title}")
                    
                    # 1. タイトルの復元
                    if is_scheduled_title:
                        title = title.replace(self.SCHEDULED_PREFIX, "", 1).strip()
                        task['title'] = title
                        
                    # 2. メモの復元 (ID部分のみ正規表現で削除する)
                    if has_event_id_note:
                        # 改行を含めて綺麗に消すパターン: 0個以上の改行 + [Ref:EventID:任意の文字列]
                        # re.sub でパターンに一致する部分を空文字列に置換
                        notes = re.sub(r'\n*\[Ref:EventID:.*?\]\n*', '', notes)
                        task['notes'] = notes.strip()
                        
                    # 3. Tasks API 経由で更新
                    self.tasks.update_task(list_id, task_id, task)
                    self.state.remove_link(task_id) # ステートの紐付けも解除
                    
                    undo_count += 1
                    
        self.log(f"元に戻す(Undo) 処理が完了しました。（更新件数: {undo_count}件）")

