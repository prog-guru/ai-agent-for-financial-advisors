# example_usage.py
"""
Example usage of the RAG system for client questions

This demonstrates how the system can answer questions like:
- "Who mentioned their kid plays baseball?"
- "Why did greg say he wanted to sell AAPL stock?"

The system uses:
1. Gmail API to import emails
2. HubSpot API to import contacts and notes
3. Sentence transformers for embeddings
4. pgvector for similarity search
5. OpenAI for generating responses with context
"""

import asyncio
import requests
from app.services.rag import rag_service
from app.services.data_sync import data_sync_service

# Example questions the system can answer:
EXAMPLE_QUESTIONS = [
    "Who mentioned their kid plays baseball?",
    "Why did greg say he wanted to sell AAPL stock?",
    "Which clients are interested in real estate?",
    "Who works at Microsoft?",
    "What did Sarah say about her vacation plans?",
    "Which contacts mentioned retirement planning?",
    "Who has kids in college?",
    "What companies are our clients working for?",
]

def demo_api_usage():
    """
    Demo API endpoints for the RAG system
    """
    base_url = "http://localhost:8001/api"
    
    print("=== RAG System API Demo ===\n")
    
    print("1. Sync user data (Gmail + HubSpot):")
    print(f"POST {base_url}/rag/sync-data")
    print("Response: {'message': 'Data sync started in background'}\n")
    
    print("2. Ask questions about clients:")
    print(f"POST {base_url}/rag/chat")
    print("Body: {'content': 'Who mentioned their kid plays baseball?'}")
    print("Response: AI answer based on email/HubSpot context\n")
    
    print("3. Search documents:")
    print(f"GET {base_url}/rag/search?query=baseball&limit=5")
    print("Response: Relevant emails/notes with similarity scores\n")
    
    print("4. Get data statistics:")
    print(f"GET {base_url}/rag/stats")
    print("Response: Count of emails, contacts, notes, embeddings\n")

def demo_workflow():
    """
    Demo the complete workflow
    """
    print("=== Complete RAG Workflow ===\n")
    
    print("Step 1: User connects Gmail and HubSpot accounts")
    print("- OAuth flow for Gmail (existing)")
    print("- OAuth flow for HubSpot (existing)\n")
    
    print("Step 2: System syncs data in background")
    print("- Fetches emails from Gmail API")
    print("- Fetches contacts and notes from HubSpot API")
    print("- Generates embeddings using sentence-transformers")
    print("- Stores in PostgreSQL with pgvector\n")
    
    print("Step 3: User asks questions")
    print("- System finds relevant context using similarity search")
    print("- OpenAI generates answer with context")
    print("- Response includes specific details from emails/CRM\n")
    
    print("Example interactions:")
    for i, question in enumerate(EXAMPLE_QUESTIONS[:4], 1):
        print(f"{i}. User: \"{question}\"")
        print(f"   AI: [Searches emails/notes and provides specific answer]\n")

if __name__ == "__main__":
    demo_api_usage()
    print("\n" + "="*50 + "\n")
    demo_workflow()