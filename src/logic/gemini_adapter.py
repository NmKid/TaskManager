import google.generativeai as genai
import json
from config.config import Config

class GeminiAdapter:
    def __init__(self):
        if Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp') # Or gemini-pro
        else:
            self.model = None
            print("Warning: GEMINI_API_KEY is not set.")

    def analyze_task(self, task_title, task_notes=""):
        """
        Analyzes a task to determine importance, duration, location, and potential subtasks.
        Returns a JSON object.
        """
        if not self.model:
            return None

        prompt = f"""
        You are a smart task scheduler assistant. Analyze the following task and return a JSON object.
        
        Task Title: {task_title}
        Task Notes: {task_notes}
        
        Output JSON format:
        {{
            "importance": (1-5, 5 being highest),
            "estimated_duration_minutes": (integer, default 30 if unknown),
            "location": (string or null),
            "is_fixed_time": (boolean, true if the task implies a specific time like 'Dinner at 7pm'),
            "suggested_subtasks": [
                {{"title": "Subtask 1", "estimated_duration_minutes": 15}},
                ... (only if the task is complex and needs breakdown)
            ]
        }}
        
        Return ONLY the JSON.
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Cleanup code blocks if present
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini analysis failed: {e}")
            return None

    def estimate_travel_time(self, location_from, location_to):
        """
        Estimates travel time between two locations.
        """
        if not self.model or not location_from or not location_to:
            return 30 # Default safety buffer

        prompt = f"""
        Estimate the travel time from "{location_from}" to "{location_to}" by public transport or driving (whichever is typical).
        Return ONLY the number of minutes as an integer.
        """
        
        try:
            response = self.model.generate_content(prompt)
            return int(''.join(filter(str.isdigit, response.text)))
        except:
            return 30

    def categorize_task(self, task_title, available_lists):
        """
        Determines the best list for a task from available_lists.
        Returns the name of the list.
        """
        if not self.model:
            return None

        list_names = [l['title'] for l in available_lists]
        
        prompt = f"""
        Assign the task "{task_title}" to one of the following lists: {', '.join(list_names)}.
        Return ONLY the list name. If no list is clearly appropriate, return "None".
        """
        
        try:
            response = self.model.generate_content(prompt)
            chosen_list = response.text.strip()
            if chosen_list in list_names:
                return chosen_list
            return None
        except:
            return None
