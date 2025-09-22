"""User domain model."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class UserFile:
    """User file model."""
    
    id: str
    user_id: str
    filename: str
    path: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UserTask:
    """User task history model."""
    
    id: str
    user_id: str
    agent_id: str
    title: str
    status: str
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def complete(self) -> None:
        """Mark the task as completed."""
        self.status = "completed"
        self.completed_at = datetime.now()


@dataclass
class User:
    """User domain model."""
    
    id: str
    email: str
    name: Optional[str] = None
    groups: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_login: datetime = field(default_factory=datetime.now)
    tasks: List[UserTask] = field(default_factory=list)
    files: List[UserFile] = field(default_factory=list)
    
    @classmethod
    def from_oauth(cls, user_info: Dict[str, Any]) -> "User":
        """Create a User from OAuth user information."""
        return cls(
            id=user_info.get("user_id", ""),
            email=user_info.get("email", ""),
            name=user_info.get("name"),
            groups=user_info.get("groups", []),
        )
    
    def add_task(self, task: UserTask) -> None:
        """Add a task to the user's history."""
        self.tasks.append(task)
    
    def add_file(self, file: UserFile) -> None:
        """Add a file to the user's files."""
        self.files.append(file) 