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

class TaskManagerApp:
    def __init__(self):
        self.auth = GoogleAuth()
        # Initialize lazily or on startup
        self.tasks_adapter = None
        self.calendar_adapter = None
        self.gemini_adapter = None
        self.state_manager = None
        self.synchronizer = None
        self.scheduler = None

    def initialize_logic(self):
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

            # Action wrappers
            def run_organize():
                self.synchronizer.organize_inbox()

            def run_sync():
                self.synchronizer.sync_calendar_to_tasks()

            def run_schedule():
                self.scheduler.schedule_tasks()

            # Layout
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
                        ft.ElevatedButton(
                            "振り分け (Inbox -> Lists)", 
                            on_click=run_threaded(run_organize, "Organization"), 
                            # icon="sort", # Removing icon temporarily to be safe
                            style=ft.ButtonStyle(padding=20)
                        ),
                        ft.ElevatedButton(
                            "同期 (Cal -> Tasks)", 
                            on_click=run_threaded(run_sync, "Sync"), 
                            # icon="sync", # Removing icon temporarily to be safe
                            style=ft.ButtonStyle(padding=20)
                        ),
                        ft.ElevatedButton(
                            "スケジュール実行 (Tasks -> Cal)", 
                            on_click=run_threaded(run_schedule, "Scheduling"), 
                            # icon="schedule", # Removing icon temporarily to be safe
                            style=ft.ButtonStyle(padding=20)
                        ),
                    ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
                    
                    ft.Divider(),
                    
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
