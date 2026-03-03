import flet as ft
from config.config import Config
from src.logic.auth import GoogleAuth
from src.logic.tasks_adapter import TasksAdapter
from src.logic.calendar_adapter import CalendarAdapter
from src.logic.gemini_adapter import GeminiAdapter
from src.logic.state_manager import StateManager
from src.logic.synchronizer import Synchronizer
from src.logic.scheduler import Scheduler
import sys
import threading
import time
import datetime

# GUIアプリケーションのメインクラス
# FletによるデスクトップUIを提供し、各種ロジックの実行を管理する。
class TaskManagerApp:
    def __init__(self):
        # 認証機能は起動時にインスタンス化しておく
        self.auth = GoogleAuth()
        # 各種アダプタやロジックの実体は、実行ボタンが押されたタイミング等で遅延初期化(Lazy Init)する
        self.tasks_adapter = None
        self.calendar_adapter = None
        self.gemini_adapter = None
        self.state_manager = None
        self.synchronizer = None
        self.scheduler = None

    def initialize_logic(self):
        # 既に初期化済みの場合はスキップ
        if self.synchronizer and self.scheduler:
            return

        creds = self.auth.authenticate()
        self.tasks_adapter = TasksAdapter(self.auth)
        self.calendar_adapter = CalendarAdapter(self.auth)
        self.gemini_adapter = GeminiAdapter()
        self.state_manager = StateManager()
        
        self.synchronizer = Synchronizer(
            self.tasks_adapter, 
            self.calendar_adapter, 
            self.state_manager, 
            self.gemini_adapter
        )
        self.scheduler = Scheduler(
            self.tasks_adapter, 
            self.calendar_adapter, 
            self.state_manager, 
            self.gemini_adapter
        )

    def main(self, page: ft.Page):
        try:
            page.title = "Task Manager"
            page.window_width = 800
            page.window_height = 600
            
            # Simple test to verify rendering works immediately
            page.add(ft.Text("Initializing Task Manager...", color="green")) 
            page.update()

            # UI Elements
            log_view = ft.Column(scroll=ft.ScrollMode.ALWAYS, expand=True)
            
            # Log function
            def ui_log(message):
                print(message)
                log_view.controls.append(ft.Text(str(message).strip(), selectable=True, font_family="Consolas"))
                try:
                    page.update()
                except:
                    pass

            def run_threaded(target_func, name):
                def wrapper(e):
                    btn = e.control
                    btn.disabled = True
                    ui_log(f"--- Starting {name} ---")
                    page.update()
                    
                    def worker():
                        try:
                            self.initialize_logic()
                            target_func()
                            ui_log(f"--- {name} Complete ---")
                        except Exception as ex:
                            ui_log(f"Error in {name}: {ex}")
                            import traceback
                            traceback.print_exc()
                        finally:
                            btn.disabled = False
                            try:
                                page.update()
                            except:
                                pass
                    
                    threading.Thread(target=worker, daemon=True).start()
                return wrapper

            # 各種処理のラッパー関数 (別スレッドで実行)
            def run_organize():
                # ■メモにあるタスクを各■リストに振り分ける処理
                self.synchronizer.organize_inbox()

            def refresh_approval_ui():
                """保留中の分割タスクをUIに表示し、承認ボタンを提供する"""
                approval_list = page.get_control("approval_list")
                if not approval_list:
                    return
                approval_list.controls.clear()
                
                if not self.scheduler or not self.scheduler.pending_split_tasks:
                     approval_list.controls.append(ft.Text("現在、承認待ちのタスクはありません。", color="grey"))
                else:
                     for idx, p_task in enumerate(self.scheduler.pending_split_tasks):
                         subtasks_str = ", ".join(p_task["analysis"].get("recommended_subtasks", []))
                         
                         def make_approve_handler(task_index, t_data):
                              def handler(e):
                                  ui_log(f"[{t_data['title']}] の分割を承認し、スケジュール登録を再開します...")
                                  # 1. 保留リストから削除
                                  self.scheduler.pending_split_tasks.pop(task_index)
                                  refresh_approval_ui() # UI更新
                                  
                                  # 2. スケジュール強制実行 (バックグラウンド)
                                  def process_approved():
                                      try:
                                          freebusy_data = self.calendar.get_free_busy(
                                              datetime.datetime.now(datetime.timezone.utc), 
                                              datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=14)
                                          )
                                          # Scheduler の単一処理や分割処理を強制的に呼び出す
                                          # ここでは簡易的にサブタスク化して登録するロジックを再実行 (scheduler本体にメソッドを切り出すのが望ましいがインラインで処理)
                                          list_id = t_data["list_id"]
                                          task_id = t_data["original_task_id"]
                                          title = t_data["title"]
                                          analysis = t_data["analysis"]
                                          subtasks = analysis.get("recommended_subtasks", [])
                                          
                                          # 親タスク更新
                                          new_title = f"{self.scheduler.SPLIT_PREFIX}{title}"
                                          self.tasks_adapter.update_task(list_id, task_id, {"title": new_title})
                                          
                                          for str_sub in subtasks:
                                              new_task_body = self.tasks_adapter.insert_task(list_id, str_sub, f"Parent: {title}")
                                              if new_task_body:
                                                   self.scheduler._schedule_single_task(list_id, new_task_body, analysis, freebusy_data)
                                          ui_log(f"-> 承認されたタスクのスケジュール登録が完了しました。")
                                      except Exception as ex:
                                          ui_log(f"承認タスクの処理中にエラー: {ex}")
                                          
                                  threading.Thread(target=process_approved, daemon=True).start()
                              return handler

                         row = ft.Row([
                             ft.Icon(ft.icons.WARNING, color="orange"),
                             ft.Text(f"「{p_task['title']}」が {len(p_task['analysis'].get('recommended_subtasks', []))} 個に分割されました。", tooltip=subtasks_str, expand=True),
                             ft.ElevatedButton("内容を承認して登録", on_click=make_approve_handler(idx, p_task), bgcolor="green", color="white")
                         ])
                         approval_list.controls.append(row)
                         
                try:
                    page.update()
                except:
                    pass

            def run_schedule():
                # Tasks -> Calendarへのスケジューリング処理（Cal -> Tasksの同期は行わない）
                self.scheduler.schedule_tasks()
                refresh_approval_ui()
                
            # Layout: UIの主構成
            page.scroll = ft.ScrollMode.AUTO
            page.clean()
            
            page.add(
                ft.Column([
                    ft.Container(
                        content=ft.Row([
                            # ft.Icon("task_alt", size=30, color="blue"), # Removed for debugging
                            ft.Text("[Icon]", size=24, color="blue"),
                            ft.Text("Task Manager AI Scheduler", size=24, weight="bold")
                        ], alignment=ft.MainAxisAlignment.CENTER),
                        padding=10
                    ),
                    
                    ft.Divider(),
                    
                    ft.Row([
                        # 振り分け処理ボタン
                        ft.ElevatedButton(
                            "振り分け (Inbox -> Lists)", 
                            on_click=run_threaded(run_organize, "Organization"), 
                            style=ft.ButtonStyle(padding=20)
                        ),
                        # スケジュール実行ボタン (Tasks -> Calのみ)
                        ft.ElevatedButton(
                            "スケジュール実行 (Tasks -> Cal)", 
                            on_click=run_threaded(run_schedule, "Scheduling"), 
                            style=ft.ButtonStyle(padding=20)
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    
                    ft.Divider(),
                    
                    # 承認待ちタスクの表示エリア
                    ft.Text("確認・承認が必要なタスク (過剰分割保留):", weight="bold", color="orange"),
                    ft.Container(id="approval_container", content=ft.Column(id="approval_list"), margin=ft.margin.only(bottom=10)),

                    ft.Text("Logs (Check Console for Details):", weight="bold"),
                    
                    ft.Container(
                        content=log_view,
                        border=ft.border.all(1, "grey"), # Changed from grey300 to grey
                        border_radius=5,
                        padding=10,
                        height=300,
                        bgcolor="white"
                    )
                ])
            )
            
            page.update()
            
        except Exception as e:
            print(f"CRITICAL UI ERROR: {e}")
            import traceback
            traceback.print_exc()
            page.add(ft.Text(f"Error loading UI: {e}", color="red"))
            page.update()

if __name__ == "__main__":
    app_instance = TaskManagerApp()
    ft.app(target=app_instance.main)
