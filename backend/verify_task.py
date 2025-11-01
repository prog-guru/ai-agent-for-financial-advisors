#!/usr/bin/env python3
from app.db import get_db
from app.models import AgentTask
import json

def verify_latest_task():
    db = next(get_db())
    
    # Get latest task
    task = db.query(AgentTask).order_by(AgentTask.id.desc()).first()
    
    if task and 'tool_results' in task.context:
        print(f"Task: {task.description}")
        print(f"Status: {task.status}")
        print("\nTools executed:")
        
        for i, result in enumerate(task.context['tool_results'], 1):
            print(f"\n{i}. {result['tool']}")
            print(f"   Args: {result['arguments']}")
            print(f"   Success: {result['result'].get('success', 'N/A')}")
            
            if result['tool'] == 'send_email' and result['result'].get('success'):
                print(f"   ✅ EMAIL SENT to: {result['arguments']['to']}")
                print(f"   Subject: {result['arguments']['subject']}")
            elif result['tool'] == 'find_contact_info' and result['result'].get('results'):
                print(f"   ✅ FOUND CONTACTS: {len(result['result']['results'])}")
                for contact in result['result']['results']:
                    print(f"      - {contact['name']} <{contact['email']}>")
            elif not result['result'].get('success'):
                print(f"   ❌ FAILED: {result['result'].get('error', 'Unknown error')}")
    else:
        print("No task with tool results found")

if __name__ == "__main__":
    verify_latest_task()