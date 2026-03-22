from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class IterationStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class Message(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)

class ProjectState(BaseModel):
    project_name: str
    goal: str
    current_iteration: int = 0
    max_iterations: int = 20
    status: IterationStatus = IterationStatus.IN_PROGRESS
    history: List[Message] = []
    artifacts: Dict[str, str] = {}  # filepath -> content
    metrics: Dict[str, Any] = {}
    
    def add_message(self, role: str, content: str):
        self.history.append(Message(role=role, content=content))

class EngineConfig(BaseModel):
    api_key: Optional[str] = None
    model: str = "gpt-4-turbo"
    temperature: float = 0.7
    system_prompt_override: Optional[str] = None
