import pytest
from fastapi.testclient import TestClient
from sandbox.main import app
from sandbox.api.agent_run import AgentRunRequest, Context, Message, Section, Block


client = TestClient(app)


def test_agent_run_endpoint_exists():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_run_basic_request():
    request_data = {
        "thread_id": "test-thread-1",
        "messages": [
            {"role": "user", "content": "Rewrite the introduction"}
        ],
        "context": {
            "sections": [
                {"id": "intro", "title": "Introduction"}
            ],
            "blocks": [
                {"id": "block-1", "markdown_text": "This is the introduction."}
            ]
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "agent_message" in data
    assert "proposed_edits" in data
    assert isinstance(data["proposed_edits"], list)


def test_agent_run_response_format():
    request_data = {
        "thread_id": "test-thread-2",
        "messages": [
            {"role": "user", "content": "Add a new section"}
        ],
        "context": {
            "sections": [],
            "blocks": []
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    data = response.json()
    
    assert isinstance(data["agent_message"], str)
    assert isinstance(data["proposed_edits"], list)


def test_agent_run_invalid_request_missing_thread_id():
    request_data = {
        "messages": [
            {"role": "user", "content": "Test"}
        ],
        "context": {
            "sections": [],
            "blocks": []
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    assert response.status_code == 422


def test_agent_run_invalid_request_missing_context():
    request_data = {
        "thread_id": "test-thread-3",
        "messages": [
            {"role": "user", "content": "Test"}
        ]
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    assert response.status_code == 422


def test_agent_run_invalid_message_format():
    request_data = {
        "thread_id": "test-thread-4",
        "messages": [
            {"role": "invalid_role", "content": "Test"}
        ],
        "context": {
            "sections": [],
            "blocks": []
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    assert response.status_code in [200, 422]


def test_agent_run_empty_messages():
    request_data = {
        "thread_id": "test-thread-5",
        "messages": [],
        "context": {
            "sections": [],
            "blocks": []
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "agent_message" in data


def test_agent_run_with_conversation_history():
    request_data = {
        "thread_id": "test-thread-6",
        "messages": [
            {"role": "user", "content": "Rewrite intro"},
            {"role": "assistant", "content": "Here's the rewritten intro."},
            {"role": "user", "content": "Make it shorter"}
        ],
        "context": {
            "sections": [{"id": "intro", "title": "Introduction"}],
            "blocks": [{"id": "block-1", "markdown_text": "Long introduction text."}]
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    assert response.status_code == 200
    data = response.json()
    assert "agent_message" in data
    assert "proposed_edits" in data


def test_agent_run_proposed_edits_format():
    request_data = {
        "thread_id": "test-thread-7",
        "messages": [
            {"role": "user", "content": "Update block"}
        ],
        "context": {
            "sections": [],
            "blocks": [{"id": "block-1", "markdown_text": "Original text"}]
        }
    }
    
    response = client.post("/v1/agent/run", json=request_data)
    data = response.json()
    
    for edit in data["proposed_edits"]:
        assert "block_id" in edit
        assert "new_markdown_text" in edit
        assert isinstance(edit["block_id"], str)
        assert isinstance(edit["new_markdown_text"], str)
