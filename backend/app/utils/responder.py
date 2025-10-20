# app/utils/responder.py
from typing import Optional

def mock_assistant_reply(user_text: str) -> str:
    # Extremely simple demo logic you can replace with an LLM later
    if "bill" in user_text.lower() and "tim" in user_text.lower():
        return "Sure, here are some recent meetings that you, Bill, and Tim all attended. I found 2 in May."
    if "clear" in user_text.lower():
        return "Okay, I cleared the chat."
    return "Got it. (Demo reply) I can also summarize meetings or schedule a follow-up."
