# app/routers/agent.py
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import logging

from ..db import get_db
from ..models import User, AgentTask, AgentInstruction
from ..schemas import AgentTaskOut, AgentTaskCreate, AgentInstructionOut, AgentInstructionCreate
from ..security import verify_session_jwt
from ..services.agent import agent_service

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from session cookie"""
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    user_data = verify_session_jwt(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    user = db.query(User).filter(User.sub == user_data["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

@router.post("/tasks", response_model=AgentTaskOut)
async def create_task(
    task_data: AgentTaskCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """Create a new task for the agent"""
    user = await get_current_user(request, db)
    
    task = await agent_service.create_task(db, user, task_data.description, task_data.context)
    
    # Process task in background
    background_tasks.add_task(agent_service.process_task, db, task)
    
    return AgentTaskOut(
        id=task.id,
        description=task.description,
        status=task.status,
        context=task.context,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at
    )

@router.get("/tasks", response_model=List[AgentTaskOut])
async def get_tasks(request: Request, db: Session = Depends(get_db)):
    """Get all tasks for the current user"""
    user = await get_current_user(request, db)
    
    tasks = db.query(AgentTask).filter(AgentTask.user_id == user.id).order_by(AgentTask.created_at.desc()).all()
    
    return [
        AgentTaskOut(
            id=task.id,
            description=task.description,
            status=task.status,
            context=task.context,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at
        )
        for task in tasks
    ]

@router.get("/tasks/{task_id}", response_model=AgentTaskOut)
async def get_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    """Get a specific task"""
    user = await get_current_user(request, db)
    
    task = db.query(AgentTask).filter(
        AgentTask.id == task_id,
        AgentTask.user_id == user.id
    ).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return AgentTaskOut(
        id=task.id,
        description=task.description,
        status=task.status,
        context=task.context,
        result=task.result,
        created_at=task.created_at,
        updated_at=task.updated_at
    )

@router.post("/instructions", response_model=AgentInstructionOut)
async def add_instruction(
    instruction_data: AgentInstructionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Add an ongoing instruction for the agent"""
    user = await get_current_user(request, db)
    
    instruction = agent_service.add_instruction(db, user, instruction_data.instruction)
    
    return AgentInstructionOut(
        id=instruction.id,
        instruction=instruction.instruction,
        is_active=instruction.is_active,
        created_at=instruction.created_at
    )

@router.get("/instructions", response_model=List[AgentInstructionOut])
async def get_instructions(request: Request, db: Session = Depends(get_db)):
    """Get all instructions for the current user"""
    user = await get_current_user(request, db)
    
    instructions = db.query(AgentInstruction).filter(
        AgentInstruction.user_id == user.id
    ).order_by(AgentInstruction.created_at.desc()).all()
    
    return [
        AgentInstructionOut(
            id=inst.id,
            instruction=inst.instruction,
            is_active=inst.is_active,
            created_at=inst.created_at
        )
        for inst in instructions
    ]

@router.put("/instructions/{instruction_id}/toggle")
async def toggle_instruction(
    instruction_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Toggle an instruction active/inactive"""
    user = await get_current_user(request, db)
    
    instruction = db.query(AgentInstruction).filter(
        AgentInstruction.id == instruction_id,
        AgentInstruction.user_id == user.id
    ).first()
    
    if not instruction:
        raise HTTPException(status_code=404, detail="Instruction not found")
    
    instruction.is_active = not instruction.is_active
    db.commit()
    
    return {"success": True, "is_active": instruction.is_active}

@router.post("/process-pending")
async def process_pending_tasks(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """Manually trigger processing of pending tasks"""
    user = await get_current_user(request, db)
    
    pending_tasks = db.query(AgentTask).filter(
        AgentTask.user_id == user.id,
        AgentTask.status == "pending"
    ).all()
    
    for task in pending_tasks:
        background_tasks.add_task(agent_service.process_task, db, task)
    
    return {"message": f"Processing {len(pending_tasks)} pending tasks"}

@router.post("/webhook/gmail")
async def gmail_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Gmail webhook notifications"""
    # This would be called by Gmail push notifications
    # For now, we'll simulate with a simple endpoint
    
    # In a real implementation, you'd:
    # 1. Verify the webhook signature
    # 2. Parse the notification data
    # 3. Identify the user
    # 4. Trigger proactive actions
    
    data = await request.json()
    
    # For demo purposes, assume we have user context
    # In reality, you'd extract this from the webhook data
    user_id = data.get("user_id")  # This would come from webhook processing
    
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            background_tasks.add_task(
                agent_service.check_proactive_actions,
                db, user, "gmail_notification", data
            )
    
    return {"status": "processed"}

@router.post("/webhook/calendar")
async def calendar_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Calendar webhook notifications"""
    data = await request.json()
    
    user_id = data.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            background_tasks.add_task(
                agent_service.check_proactive_actions,
                db, user, "calendar_notification", data
            )
    
    return {"status": "processed"}

@router.post("/webhook/hubspot")
async def hubspot_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle HubSpot webhook notifications"""
    data = await request.json()
    
    user_id = data.get("user_id")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            background_tasks.add_task(
                agent_service.check_proactive_actions,
                db, user, "hubspot_notification", data
            )
    
    return {"status": "processed"}