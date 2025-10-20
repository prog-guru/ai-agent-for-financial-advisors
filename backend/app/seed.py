# app/seed.py
from sqlalchemy.orm import Session
from .models import Meeting, Message
from datetime import datetime

def seed(db: Session):
    return
    # Only seed if empty
    if db.query(Meeting).count() == 0:
        you = {"id": "me", "name": "You"}
        bill = {"id": "p1", "name": "Bill Junior"}
        tim = {"id": "p2", "name": "Tim Novak"}

        m1 = Meeting(
            title="Quarterly All Team Meeting",
            start_iso="2025-05-08T12:00:00Z",
            end_iso="2025-05-08T13:30:00Z",
            attendees={"people": [you, bill, tim]},
        )
        m2 = Meeting(
            title="Strategy review",
            start_iso="2025-05-16T13:00:00Z",
            end_iso="2025-05-16T14:00:00Z",
            attendees={"people": [you, tim]},
        )
        db.add_all([m1, m2])

    if db.query(Message).count() == 0:
        db.add(Message(role="assistant", content="I can answer questions about any Jump meeting. What do you want to know?"))

    db.commit()
