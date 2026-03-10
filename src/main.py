import sys
import os
import warnings
from pathlib import Path

# filter warning outputs to keep console clean
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))

from src.ui.app import TaskManagerApp
import flet as ft

def main():
    app = TaskManagerApp()
    ft.app(target=app.main)

if __name__ == "__main__":
    main()
