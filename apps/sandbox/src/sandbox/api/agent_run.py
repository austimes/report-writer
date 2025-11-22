from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Block(BaseModel):
    id: str
    markdown_text: str


class Section(BaseModel):
    id: str
    title: str


class Context(BaseModel):
    sections: list[Section]
    blocks: list[Block]


class Message(BaseModel):
    role: str
    content: str


class AgentRunRequest(BaseModel):
    thread_id: str
    messages: list[Message]
    context: Context


class ProposedEdit(BaseModel):
    block_id: str
    new_markdown_text: str


class AgentRunResponse(BaseModel):
    agent_message: str
    proposed_edits: list[ProposedEdit]


@router.post("/agent/run", response_model=AgentRunResponse)
async def agent_run(request: AgentRunRequest):
    return AgentRunResponse(
        agent_message="I'm ready to help you with your report. This is a stub response for now.",
        proposed_edits=[],
    )
