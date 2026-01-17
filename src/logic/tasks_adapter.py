from googleapiclient.discovery import build
from config.config import Config

class TasksAdapter:
    def __init__(self, auth_service):
        self.service = auth_service.get_service('tasks', 'v1')

    def get_task_lists(self):
        """Returns a list of all task lists."""
        results = self.service.tasklists().list().execute()
        items = results.get('items', [])
        return items

    def get_target_lists(self):
        """Returns lists that start with the target prefix (■)."""
        all_lists = self.get_task_lists()
        return [l for l in all_lists if l['title'].startswith(Config.TARGET_LIST_PREFIX)]

    def get_inbox_list(self):
        """Returns the Inbox list (■メモ)."""
        all_lists = self.get_task_lists()
        for l in all_lists:
            if l['title'] == Config.INBOX_LIST_NAME:
                return l
        return None

    def get_tasks_in_list(self, tasklist_id):
        """Returns all non-completed tasks in a specific list."""
        results = self.service.tasks().list(
            tasklist=tasklist_id,
            showCompleted=False,
            showHidden=False
        ).execute()
        return results.get('items', [])

    def create_task(self, tasklist_id, title, notes=None, due=None):
        """Creates a new task."""
        task_body = {
            'title': title,
            'notes': notes,
            'due': due
        }
        return self.service.tasks().insert(
            tasklist=tasklist_id,
            body=task_body
        ).execute()

    def update_task_list(self, task_id, tasklist_id_source, tasklist_id_dest):
        """Moves a task from one list to another (simulated by delete and insert)."""
        # Google Tasks API doesn't support 'move' between lists directly with simple call 
        # (needs get, insert to new, delete from old)
        task = self.service.tasks().get(tasklist=tasklist_id_source, task=task_id).execute()
        
        # Insert to new list
        new_task = self.service.tasks().insert(
            tasklist=tasklist_id_dest,
            body=task
        ).execute()
        
        # Delete from old list
        self.service.tasks().delete(tasklist=tasklist_id_source, task=task_id).execute()
        
        return new_task

    def update_task(self, tasklist_id, task_id, body):
        """Updates a task."""
        return self.service.tasks().patch(
            tasklist=tasklist_id,
            task=task_id,
            body=body
        ).execute()
