import sys
import os

sys.path.append(os.getcwd())

from src.logic.auth import GoogleAuth
from src.logic.tasks_adapter import TasksAdapter

def main():
    print("Listing all task lists...")
    auth = GoogleAuth()
    auth.authenticate()
    tasks = TasksAdapter(auth)
    
    lists = tasks.get_task_lists()
    for l in lists:
        print(f"ID: {l['id']}, Title: '{l['title']}'")

if __name__ == "__main__":
    main()
