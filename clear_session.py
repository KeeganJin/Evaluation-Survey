import json
import os

SESSION_PATH = os.path.join('.', 'database', 'sessions.json')

def clear_sessions():
    with open(SESSION_PATH, 'w') as f:
        json.dump({}, f, indent=2)
    print(f"✅ Cleared: {SESSION_PATH}")

if __name__ == '__main__':
    clear_sessions()