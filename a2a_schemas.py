"""A2A Protocol Schema Definitions for validation.

These schemas match the official A2A specification and can be used
to validate agent cards and other A2A protocol messages.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ProviderSchema(BaseModel):
    """Provider information schema."""
    name: str
    organization: str
    url: HttpUrl
    

class SkillSchema(BaseModel):
    """Skill definition schema."""
    id: str
    name: str
    description: str
    tags: Optional[List[str]] = []
    

class CapabilitiesSchema(BaseModel):
    """Agent capabilities schema."""
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False
    extensions: List[Any] = []
    

class AgentCardSchema(BaseModel):
    """Complete A2A Agent Card schema for validation."""
    # Required fields
    name: str = Field(..., description="Agent name")
    description: str = Field(..., description="Agent description")
    version: str = Field(..., description="Agent version")
    url: HttpUrl = Field(..., description="Agent base URL")
    protocolVersion: str = Field(..., pattern="^a2a/v\\d+$", description="A2A protocol version")
    
    # Input/Output modes
    defaultInputModes: List[str] = Field(default=["text"])
    defaultOutputModes: List[str] = Field(default=["text"])
    
    # Capabilities
    capabilities: CapabilitiesSchema
    
    # Skills (at least one required)
    skills: List[SkillSchema] = Field(..., min_length=1)
    
    # Provider info
    provider: ProviderSchema
    
    @field_validator('skills')
    def validate_skills(cls, v):
        if not v:
            raise ValueError("At least one skill must be defined")
        return v


class MessagePartSchema(BaseModel):
    """Message part schema."""
    kind: Literal["text", "data", "image", "tool_use", "tool_result"]
    text: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    

class MessageSchema(BaseModel):
    """Message schema."""
    kind: Literal["message"]
    message_id: str = Field(..., alias="message_id")  # Note: underscore not camelCase
    parts: List[MessagePartSchema]
    role: Literal["user", "agent", "system"]
    

class TaskStatusSchema(BaseModel):
    """Task status schema."""
    state: Literal["pending", "working", "completed", "failed", "cancelled"]
    timestamp: str
    message: Optional[MessageSchema] = None
    error: Optional[Dict[str, Any]] = None
    

class TaskSchema(BaseModel):
    """Task response schema."""
    id: str
    kind: Literal["task"]
    contextId: Optional[str] = None
    status: TaskStatusSchema
    

def validate_agent_card(card: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate an agent card against the A2A schema.
    
    Returns:
        tuple: (is_valid, list_of_errors)
    """
    try:
        AgentCardSchema(**card)
        return True, []
    except Exception as e:
        # Parse Pydantic validation errors
        if hasattr(e, 'errors'):
            errors = []
            for err in e.errors():
                loc = '.'.join(str(l) for l in err['loc'])
                msg = err['msg']
                errors.append(f"{loc}: {msg}")
            return False, errors
        else:
            return False, [str(e)]


def validate_task_response(response: Dict[str, Any]) -> tuple[bool, List[str]]:
    """Validate a task response against the A2A schema.
    
    Returns:
        tuple: (is_valid, list_of_errors)
    """
    try:
        TaskSchema(**response)
        return True, []
    except Exception as e:
        if hasattr(e, 'errors'):
            errors = []
            for err in e.errors():
                loc = '.'.join(str(l) for l in err['loc'])
                msg = err['msg']
                errors.append(f"{loc}: {msg}")
            return False, errors
        else:
            return False, [str(e)]