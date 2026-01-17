from src.ui.app import TaskManagerApp
import flet as ft

def main():
    app = TaskManagerApp()
    ft.app(target=app.main)

if __name__ == "__main__":
    main()
