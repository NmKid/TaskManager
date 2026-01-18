import sys
import os
from datetime import datetime, timedelta
import time

# Add project root to path
sys.path.append(os.getcwd())

from src.logic.auth import GoogleAuth
from src.logic.calendar_adapter import CalendarAdapter
from src.logic.tasks_adapter import TasksAdapter
from src.logic.synchronizer import Synchronizer
from src.logic.state_manager import StateManager
from src.logic.gemini_adapter import GeminiAdapter # Mock or unused in this test

class MockGeminiAdapter:
    def categorize_task(self, title, target_lists):
        return None

def verify_sync():
    print("=== Starting Sync Verification ===")
    
    # 1. Setup
    auth = GoogleAuth()
    creds = auth.authenticate()
    
    calendar = CalendarAdapter(auth)
    tasks = TasksAdapter(auth)
    state = StateManager()
    gemini = MockGeminiAdapter()
    
    synchronizer = Synchronizer(tasks, calendar, state, gemini)
    
    # 2. Create Test Event
    now = datetime.now()
    start_time = now + timedelta(hours=1)
    end_time = start_time + timedelta(hours=1)
    summary = f"Test Event {int(time.time())}"
    
    print(f"Creating test event: {summary}")
    event = calendar.create_event(summary, start_time, end_time)
    event_id = event['id']
    print(f"Event created with ID: {event_id}")
    
    # Allow some time for API propagation if needed, though usually instant
    time.sleep(2)
    
    # 3. Run Sync
    print("Running sync_calendar_to_tasks...")
    synchronizer.sync_calendar_to_tasks()
    
    # 4. Verify
    print("Verifying task creation...")
    inbox = tasks.get_inbox_list()
    if not inbox:
        print("Error: Inbox list not found!")
        return
    
    inbox_tasks = tasks.get_tasks_in_list(inbox['id'])
    
    found_task = None
    expected_title = f"【予定済】{summary}"
    
    for task in inbox_tasks:
        if task['title'] == expected_title:
            found_task = task
            break
            
    if found_task:
        print("SUCCESS: Task found!")
        print(f"Task Title: {found_task['title']}")
        print(f"Task Notes: {found_task.get('notes', '')}")
        
        if f"[Ref:EventID:{event_id}]" in found_task.get('notes', ''):
            print("SUCCESS: Event ID reference found in notes.")
        else:
            print("FAILURE: Event ID reference missing from notes.")
            
        # 5. Cleanup
        print("Cleaning up...")
        try:
            tasks.service.tasks().delete(tasklist=inbox['id'], task=found_task['id']).execute()
            print("Test task deleted.")
        except Exception as e:
            print(f"Failed to delete test task: {e}")
            
    else:
        print(f"FAILURE: Task with title '{expected_title}' not found.")
    
    try:
        calendar.service.events().delete(calendarId='primary', eventId=event_id).execute()
        print("Test event deleted.")
    except Exception as e:
        print(f"Failed to delete test event: {e}")

if __name__ == "__main__":
    verify_sync()
