from datetime import datetime, timedelta
import dateutil.parser
from config.config import Config

class Scheduler:
    def __init__(self, tasks_adapter, calendar_adapter, state_manager, gemini_adapter):
        self.tasks = tasks_adapter
        self.calendar = calendar_adapter
        self.state = state_manager
        self.gemini = gemini_adapter

    def schedule_tasks(self):
        """
        3.4 Scheduling: Tasks -> Calendar
        Analyzes tasks and schedules them into free slots.
        """
        print("Starting Scheduling...")
        target_lists = self.tasks.get_target_lists()
        all_tasks = []
        for task_list in target_lists:
            tasks = self.tasks.get_tasks_in_list(task_list['id'])
            for t in tasks:
                t['list_id'] = task_list['id']
            all_tasks.extend(tasks)

        # Filter unscheduled tasks
        unscheduled_tasks = []
        for task in all_tasks:
            title = task['title']
            notes = task.get('notes', '')
            
            # Skip conditions
            if "【予定済】" in title:
                continue
            if "[Ref:EventID:" in notes:
                continue
            
            unscheduled_tasks.append(task)

        if not unscheduled_tasks:
            print("No unscheduled tasks found.")
            return

        # Sort by Due Date (nulls last)
        def get_due_date(t):
            d = t.get('due')
            return d if d else "9999-12-31" 
        
        unscheduled_tasks.sort(key=get_due_date)

        # Get existing events to find free slots
        now = datetime.now().replace(second=0, microsecond=0)
        if now.hour < Config.WORK_START_HOUR:
             now = now.replace(hour=Config.WORK_START_HOUR, minute=0)
        
        search_end = now + timedelta(days=Config.SCHEDULING_DAYS)
        existing_events = self.calendar.get_events(now, search_end)
        
        # Simple Greedy Slot Finder
        current_search_time = now
        
        for task in unscheduled_tasks:
            print(f"Processing task: {task['title']}")
            
            # Analyze Task
            analysis = self.gemini.analyze_task(task['title'], task.get('notes', ''))
            
            duration_minutes = 30 # Default
            if analysis and analysis.get("estimated_duration_minutes"):
                duration_minutes = analysis["estimated_duration_minutes"]
            
            # Find Slot
            slot_start = self._find_first_free_slot(current_search_time, duration_minutes, existing_events)
            
            if not slot_start:
                print(f"Could not find a slot for {task['title']} within {Config.SCHEDULING_DAYS} days.")
                continue

            slot_end = slot_start + timedelta(minutes=duration_minutes)
            
            # Create Event
            try:
                print(f"Scheduling at {slot_start}")
                event = self.calendar.create_event(
                    summary=task['title'],
                    start_time=slot_start,
                    end_time=slot_end,
                    description=f"Task ID: {task['id']}\n{task.get('notes', '')}"
                )
                
                # Update Task
                new_title = f"【予定済】{task['title']}"
                new_notes = f"{task.get('notes', '')}\n[Ref:EventID:{event['id']}]"
                
                self.tasks.update_task(task['list_id'], task['id'], {
                    'title': new_title,
                    'notes': new_notes
                })
                
                self.state.set_mapping(task['id'], event['id'])
                
                # Add to existing_events so next task avoids this slot
                existing_events.append({
                    'start': {'dateTime': slot_start.isoformat()},
                    'end': {'dateTime': slot_end.isoformat()}
                })
                # Re-sort events just in case
                existing_events.sort(key=lambda x: x['start'].get('dateTime', ''))
                
                # Advance search time slightly to avoid tight packing if desired
                current_search_time = slot_start 

            except Exception as e:
                print(f"Failed to schedule task {task['title']}: {e}")

    def _find_first_free_slot(self, start_time, duration_minutes, events):
        """
        Finds the first time slot of 'duration_minutes' that doesn't overlap with 'events'.
        Respects WORK_START_HOUR and WORK_END_HOUR.
        """
        candidate = start_time
        search_limit = start_time + timedelta(days=Config.SCHEDULING_DAYS)
        
        while candidate < search_limit:
            # Check Work Hours
            if candidate.hour < Config.WORK_START_HOUR:
                candidate = candidate.replace(hour=Config.WORK_START_HOUR, minute=0)
            if candidate.hour >= Config.WORK_END_HOUR:
                # Move to next day
                candidate = (candidate + timedelta(days=1)).replace(hour=Config.WORK_START_HOUR, minute=0)
                continue
            
            candidate_end = candidate + timedelta(minutes=duration_minutes)
            if candidate_end.hour > Config.WORK_END_HOUR: # Spans across end of day
                 # Move to next day
                candidate = (candidate + timedelta(days=1)).replace(hour=Config.WORK_START_HOUR, minute=0)
                continue

            # Check Overlap
            is_overlap = False
            for event in events:
                # Parse event times
                # Events have date or dateTime. We assume dateTime for this logic.
                if 'dateTime' not in event['start']:
                    continue # All day events ignored for now or treat as blocked? specific logic needed.
                
                # Simple ISO parse (naive/aware mix handling needed? Python 3.7+ fromisoformat or dateutil)
                # Google API returns RFC3339.
                evt_start = dateutil.parser.isoparse(event['start']['dateTime'])
                evt_end = dateutil.parser.isoparse(event['end']['dateTime'])
                
                # Strip timezone for comparison if needed, or ensure candidate is aware.
                # candidate is created from datetime.now() -> normally naive. 
                # evt is aware. 
                evt_start = evt_start.replace(tzinfo=None)
                evt_end = evt_end.replace(tzinfo=None)

                if max(candidate, evt_start) < min(candidate_end, evt_end):
                    is_overlap = True
                    # Jump to end of this event
                    candidate = evt_end
                    break
            
            if not is_overlap:
                return candidate
            
            # If overlap, loop continues with new candidate
        
        return None
