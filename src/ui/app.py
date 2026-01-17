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
        page.title = "Task Manager Scheduler"
        page.theme_mode = ft.ThemeMode.LIGHT
        
        # UI Elements
        log_view = ft.ListView(expand=True, spacing=10, padding=20, auto_scroll=True)

        def log(message):
            log_view.controls.append(ft.Text(message))
            page.update()
            print(message) # Also print to console

        def on_organize(e):
            try:
                log("Initializing...")
                if not self.synchronizer:
                    self.initialize_logic()
                
                log("Starting Inbox Organization...")
                self.synchronizer.organize_inbox()
                log("Organization Complete.")
            except Exception as ex:
                log(f"Error: {ex}")

        def on_sync(e):
            try:
                log("Initializing...")
                if not self.synchronizer:
                    self.initialize_logic()
                
                log("Starting Calendar -> Tasks Sync...")
                self.synchronizer.sync_calendar_to_tasks()
                log("Sync Complete.")
            except Exception as ex:
                log(f"Error: {ex}")

        def on_schedule(e):
            try:
                log("Initializing...")
                if not self.scheduler:
                    self.initialize_logic()
                
                log("Starting Scheduling...")
                self.scheduler.schedule_tasks()
                log("Scheduling Complete.")
            except Exception as ex:
                log(f"Error: {ex}")

        # Layout
        page.add(
            ft.Row([
                ft.Text("Task Manager AI Scheduler", size=24, weight="bold")
            ], alignment=ft.MainAxisAlignment.CENTER),
            ft.Divider(),
            ft.Row([
                ft.ElevatedButton("振り分け (Inbox -> Lists)", on_click=on_organize, icon=ft.icons.SORT),
                ft.ElevatedButton("同期 (Cal -> Tasks)", on_click=on_sync, icon=ft.icons.SYNC),
                ft.ElevatedButton("スケジュール実行 (Tasks -> Cal)", on_click=on_schedule, icon=ft.icons.SCHEDULE),
            ], alignment=ft.MainAxisAlignment.CENTER, spacing=20),
            ft.Divider(),
            ft.Text("Logs:", weight="bold"),
            ft.Container(
                content=log_view,
                border=ft.border.all(1, ft.colors.GREY_300),
                border_radius=5,
                height=400,
                padding=10
            )
        )

if __name__ == "__main__":
    app_instance = TaskManagerApp()
    ft.app(target=app_instance.main)
