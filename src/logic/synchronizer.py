from datetime import datetime, timedelta
from config.config import Config

class Synchronizer:
    def __init__(self, tasks_adapter, calendar_adapter, state_manager, gemini_adapter):
        self.tasks = tasks_adapter
        self.calendar = calendar_adapter
        self.state = state_manager
        self.gemini = gemini_adapter

    def sync_calendar_to_tasks(self):
        """
        3.1 Sync: Calendar -> Tasks
        Creates tasks for new calendar events in the Inbox.
        """
        print("Starting Calendar -> Tasks Sync...")
        # Get events for the next 14 days (or past 2 days to catch recent creates?)
        # Specification implies "New events created". To keep it stateless, we check a window.
        now = datetime.now()
        end = now + timedelta(days=Config.SCHEDULING_DAYS)
        
        events = self.calendar.get_events(now, end)
        
        inbox = self.tasks.get_inbox_list()
        if not inbox:
            print("Inbox list not found.")
            return

        count = 0
        for event in events:
            event_id = event['id']
            summary = event.get('summary', 'No Title')
            
            # Skip if already mapped (meaning we created it or already synced it)
            # Note: This prevents loop if we mapped Scheduler-created events correctly.
            # But we also need to check if we synced this event BEFORE.
            # Ideally state_manager allows reverse lookup event_id -> task_id or we just store synced event IDs.
            # For this MVP, we can just check if any task maps to this event_id is expensive without reverse index.
            # Let's assume StateManager tracks ALL linked items.
            
            # Since StateManager.mapping is {task_id: event_id}, we need to check values.
            if event_id in self.state.mapping.values():
                continue

            # Create Task
            print(f"New event found: {summary}. Creating task...")
            note = f"From Calendar Event\n[Ref:EventID:{event_id}]"
            
            try:
                task_title = f"【予定済】{summary}"
                task = self.tasks.create_task(inbox['id'], task_title, notes=note)
                
                # Update State
                self.state.set_mapping(task['id'], event_id)
                count += 1
            except Exception as e:
                print(f"Failed to create task for event {summary}: {e}")

        print(f"Synced {count} events to tasks.")

    def organize_inbox(self):
        """
        3.3 Organization: Inbox -> Lists
        Moves tasks from Inbox to appropriate lists based on Gemini analysis.
        """
        print("Starting Inbox Organization...")
        inbox = self.tasks.get_inbox_list()
        if not inbox:
            return

        target_lists = self.tasks.get_target_lists()
        # Remove inbox from target lists to avoid moving to itself (if inbox starts with ■)
        target_lists = [l for l in target_lists if l['id'] != inbox['id']]
        
        if not target_lists:
            print("No target lists found.")
            return

        tasks = self.tasks.get_tasks_in_list(inbox['id'])
        
        count = 0
        for task in tasks:
            title = task['title']
            
            # Skip if it's a "Scheduled" task (prevent moving processed items if desired, though org is orthogonal)
            
            destination_list_name = self.gemini.categorize_task(title, target_lists)
            
            if destination_list_name:
                # Find list ID
                dest_list = next((l for l in target_lists if l['title'] == destination_list_name), None)
                if dest_list:
                    print(f"Moving '{title}' to {destination_list_name}")
                    self.tasks.update_task_list(task['id'], inbox['id'], dest_list['id'])
                    count += 1
            else:
                print(f"No category found for '{title}', keeping in Inbox.")

        print(f"Organized {count} tasks.")
