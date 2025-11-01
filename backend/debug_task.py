#!/usr/bin/env python3
from app.db import get_db
from app.models import AgentTask, User
import json

def debug_latest_task():
    db = next(get_db())
    
    # Get latest task
    task = db.query(AgentTask).order_by(AgentTask.id.desc()).first()
    
    if task:
        print(f"Task ID: {task.id}")
        print(f"Description: {task.description}")
        print(f"Status: {task.status}")
        print(f"Context: {json.dumps(task.context, indent=2)}")
        print(f"Result: {task.result}")
        print(f"Created: {task.created_at}")
        print(f"Updated: {task.updated_at}")
        
        # Check user
        user = db.query(User).filter(User.id == task.user_id).first()
        print(f"User: {user.email if user else 'Not found'}")
        
        # Check what tools were called
        if 'tool_results' in task.context:
            print("\nTool Results:")
            for result in task.context['tool_results']:
                print(f"  Tool: {result['tool']}")
                print(f"  Args: {result['arguments']}")
                print(f"  Result: {result['result']}")
    else:
        print("No tasks found")

if __name__ == "__main__":
    debug_latest_task()