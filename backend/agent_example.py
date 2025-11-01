# agent_example.py - Example usage of the AI agent system
import asyncio
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

async def demo_agent_system():
    """Demonstrate the agent system capabilities"""
    
    # Example 1: Create a task to schedule an appointment
    print("=== Example 1: Schedule Appointment ===")
    task_data = {
        "description": "Schedule an appointment with Sara Smith",
        "context": {
            "contact_name": "Sara Smith",
            "contact_email": "sara.smith@example.com",
            "purpose": "project discussion"
        }
    }
    
    response = requests.post(f"{BASE_URL}/agent/tasks", json=task_data)
    print(f"Task created: {response.json()}")
    
    # Example 2: Add ongoing instruction
    print("\n=== Example 2: Add Ongoing Instruction ===")
    instruction_data = {
        "instruction": "When someone emails me that is not in HubSpot, please create a contact in HubSpot with a note about the email."
    }
    
    response = requests.post(f"{BASE_URL}/agent/instructions", json=instruction_data)
    print(f"Instruction added: {response.json()}")
    
    # Example 3: Another ongoing instruction
    print("\n=== Example 3: Another Ongoing Instruction ===")
    instruction_data = {
        "instruction": "When I create a contact in HubSpot, send them an email telling them thank you for being a client"
    }
    
    response = requests.post(f"{BASE_URL}/agent/instructions", json=instruction_data)
    print(f"Instruction added: {response.json()}")
    
    # Example 4: Chat with task detection
    print("\n=== Example 4: Chat with Task Detection ===")
    chat_data = {
        "content": "Send an email to john@example.com asking about our meeting next week"
    }
    
    response = requests.post(f"{BASE_URL}/chat/messages", json=chat_data)
    print(f"Chat response: {response.json()}")
    
    # Example 5: Get all tasks
    print("\n=== Example 5: View All Tasks ===")
    response = requests.get(f"{BASE_URL}/agent/tasks")
    print(f"All tasks: {response.json()}")
    
    # Example 6: Get all instructions
    print("\n=== Example 6: View All Instructions ===")
    response = requests.get(f"{BASE_URL}/agent/instructions")
    print(f"All instructions: {response.json()}")

if __name__ == "__main__":
    print("AI Agent System Demo")
    print("Make sure the backend server is running on localhost:8000")
    print("You'll need to be authenticated (have a valid session cookie)")
    
    # Note: In a real scenario, you'd need proper authentication
    # This is just to show the API structure
    
    asyncio.run(demo_agent_system())