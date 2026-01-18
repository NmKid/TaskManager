import sys
import os
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.ui.app import TaskManagerApp
import flet as ft

def main():
    app = TaskManagerApp()
    ft.app(app.main)

if __name__ == "__main__":
    main()
