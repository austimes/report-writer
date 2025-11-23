import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';

const SANDBOX_PORT = 8001;
const SANDBOX_URL = `http://localhost:${SANDBOX_PORT}`;
const SANDBOX_PATH = path.join(process.cwd(), 'apps/sandbox');

describe('Sandbox Integration Tests', () => {
  let sandboxProcess: ChildProcess;

  beforeAll(async () => {
    await new Promise<void>((resolve, reject) => {
      let hasResolved = false;
      
      sandboxProcess = spawn(
        'python',
        ['-m', 'uvicorn', 'sandbox.main:app', '--host', '0.0.0.0', '--port', SANDBOX_PORT.toString()],
        {
          cwd: SANDBOX_PATH,
          env: {
            ...process.env,
            PYTHONPATH: path.join(SANDBOX_PATH, 'src'),
            LLM_PROVIDER: 'fake',
          },
          stdio: 'pipe',
        }
      );

      sandboxProcess.stdout?.on('data', (data) => {
        const output = data.toString();
        if (!hasResolved && output.includes('Uvicorn running')) {
          hasResolved = true;
          setTimeout(resolve, 1000);
        }
      });

      sandboxProcess.stderr?.on('data', (data) => {
        const output = data.toString();
        if (!hasResolved && output.includes('Uvicorn running')) {
          hasResolved = true;
          setTimeout(resolve, 1000);
        }
      });

      sandboxProcess.on('error', (error) => {
        if (!hasResolved) {
          hasResolved = true;
          reject(error);
        }
      });

      setTimeout(() => {
        if (!hasResolved) {
          hasResolved = true;
          reject(new Error('Sandbox failed to start within timeout'));
        }
      }, 15000);
    });
  }, 20000);

  afterAll(async () => {
    if (sandboxProcess) {
      sandboxProcess.kill();
      await new Promise<void>((resolve) => {
        sandboxProcess.on('exit', () => resolve());
        setTimeout(resolve, 2000);
      });
    }
  });

  it('should respond to health check', async () => {
    const response = await fetch(`${SANDBOX_URL}/health`);
    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data).toEqual({ status: 'ok' });
  });

  it('should handle agent run request with basic input', async () => {
    const requestBody = {
      thread_id: 'test-thread-1',
      messages: [
        { role: 'user', content: 'Rewrite the introduction' },
      ],
      context: {
        sections: [
          { id: 'intro', title: 'Introduction' },
        ],
        blocks: [
          { id: 'block-1', markdown_text: 'This is the introduction.' },
        ],
      },
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    
    expect(data).toHaveProperty('agent_message');
    expect(data).toHaveProperty('proposed_edits');
    expect(typeof data.agent_message).toBe('string');
    expect(Array.isArray(data.proposed_edits)).toBe(true);
  });

  it('should return correct structure for proposed edits', async () => {
    const requestBody = {
      thread_id: 'test-thread-2',
      messages: [
        { role: 'user', content: 'Update the content' },
      ],
      context: {
        sections: [],
        blocks: [
          { id: 'block-1', markdown_text: 'Original content.' },
        ],
      },
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    const data = await response.json();
    
    if (data.proposed_edits.length > 0) {
      const edit = data.proposed_edits[0];
      expect(edit).toHaveProperty('block_id');
      expect(edit).toHaveProperty('new_markdown_text');
      expect(typeof edit.block_id).toBe('string');
      expect(typeof edit.new_markdown_text).toBe('string');
    }
  });

  it('should handle empty messages array', async () => {
    const requestBody = {
      thread_id: 'test-thread-3',
      messages: [],
      context: {
        sections: [],
        blocks: [],
      },
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('agent_message');
    expect(data).toHaveProperty('proposed_edits');
  });

  it('should handle conversation history', async () => {
    const requestBody = {
      thread_id: 'test-thread-4',
      messages: [
        { role: 'user', content: 'Rewrite this' },
        { role: 'assistant', content: 'Done' },
        { role: 'user', content: 'Make it shorter' },
      ],
      context: {
        sections: [],
        blocks: [
          { id: 'block-1', markdown_text: 'Some content.' },
        ],
      },
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data).toHaveProperty('agent_message');
    expect(data).toHaveProperty('proposed_edits');
  });

  it('should return 422 for invalid request (missing thread_id)', async () => {
    const requestBody = {
      messages: [
        { role: 'user', content: 'Test' },
      ],
      context: {
        sections: [],
        blocks: [],
      },
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    expect(response.status).toBe(422);
  });

  it('should return 422 for invalid request (missing context)', async () => {
    const requestBody = {
      thread_id: 'test-thread-5',
      messages: [
        { role: 'user', content: 'Test' },
      ],
    };

    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    expect(response.status).toBe(422);
  });

  it('should handle malformed JSON', async () => {
    const response = await fetch(`${SANDBOX_URL}/v1/agent/run`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: 'invalid json',
    });

    expect(response.status).toBe(422);
  });
});
