import json
import os

# Load intents from external JSON file
def load_intents():
    intents_path = os.path.join(os.path.dirname(__file__), "..", "data", "intents.json")
    try:
        with open(intents_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: intents.json not found at {intents_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error parsing intents.json: {e}")
        return {}

INTENTS = load_intents()

