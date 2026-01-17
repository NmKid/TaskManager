import json
from pathlib import Path
from config.config import Config

class StateManager:
    def __init__(self):
        self.state_file = Config.STATE_FILE
        self.mapping = {}  # Format: {task_id: event_id}
        self.load_state()

    def load_state(self):
        """Loads the state mapping from the JSON file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    self.mapping = json.load(f)
            except json.JSONDecodeError:
                self.mapping = {}
        else:
            self.mapping = {}

    def save_state(self):
        """Saves the current mapping to the JSON file."""
        Config.ensure_dirs()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.mapping, f, ensure_ascii=False, indent=2)

    def get_event_id(self, task_id):
        """Returns the Event ID associated with a Task ID."""
        return self.mapping.get(task_id)

    def set_mapping(self, task_id, event_id):
        """Sets a mapping between a Task ID and an Event ID."""
        self.mapping[task_id] = event_id
        self.save_state()

    def remove_mapping(self, task_id):
        """Removes a mapping for a Task ID."""
        if task_id in self.mapping:
            del self.mapping[task_id]
            self.save_state()
