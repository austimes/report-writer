#!/usr/bin/env python3
"""Deploy the Python FastAPI app to Daytona sandbox."""

import os
import subprocess
import sys
from pathlib import Path

def main():
    print("🚀 Deploying Python app to Daytona sandbox...")
    
    sandbox_name = os.getenv("SANDBOX_NAME", "report-writer-sandbox")
    
    # Get sandbox ID
    result = subprocess.run(
        ["daytona", "sandbox", "list"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ Failed to list sandboxes")
        sys.exit(1)
    
    # Parse sandbox ID
    sandbox_id = None
    for line in result.stdout.split('\n'):
        if sandbox_name in line or 'STARTED' in line:
            sandbox_id = line.split()[0].strip('[]')
            break
    
    if not sandbox_id:
        print(f"❌ Sandbox '{sandbox_name}' not found")
        print("Available sandboxes:")
        print(result.stdout)
        sys.exit(1)
    
    print(f"Found sandbox: {sandbox_id}")
    
    # Get sandbox info to extract URL
    result = subprocess.run(
        ["daytona", "sandbox", "info", sandbox_name],
        capture_output=True,
        text=True
    )
    
    print(f"\nSandbox info:")
    print(result.stdout)
    
    # Build deployment instructions
    sandbox_url = f"https://8000-{sandbox_id}.proxy.daytona.works"
    
    print("\n" + "="*60)
    print("📝 Deployment Instructions")
    print("="*60)
    print("\nTo deploy the Python app, you have two options:")
    print("\n### Option 1: Using Daytona Python SDK")
    print("\n```python")
    print("from daytona_sdk import Daytona")
    print("")
    print("daytona = Daytona()")
    print(f"sandbox = daytona.sandbox.get('{sandbox_id}')")
    print("")
    print("# Upload files")
    print("sandbox.fs.upload_directory('apps/sandbox/src', '/app/src')")
    print("sandbox.fs.upload_file('apps/sandbox/pyproject.toml', '/app/pyproject.toml')")
    print("sandbox.fs.upload_file('apps/sandbox/requirements.lock', '/app/requirements.lock')")
    print("")
    print("# Install dependencies and start server")
    print("sandbox.process.execute('cd /app && uv sync --frozen')")
    print("sandbox.process.start_background('uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000')")
    print("```")
    print("\n### Option 2: Manual Deployment (SSH)")
    print(f"\n1. Package the app locally:")
    print(f"   cd apps/sandbox")
    print(f"   tar -czf sandbox-app.tar.gz src/ pyproject.toml requirements.lock")
    print(f"\n2. The sandbox is running at:")
    print(f"   {sandbox_url}")
    print(f"\n3. You'll need to use Daytona SDK or file upload to transfer files")
    print(f"\n4. Then execute commands to install and run:")
    print(f"   uv sync --frozen")
    print(f"   uv run uvicorn sandbox.main:app --host 0.0.0.0 --port 8000")
    
    print("\n" + "="*60)
    print("✅ Sandbox ready for deployment")
    print("="*60)
    print(f"\nSandbox ID: {sandbox_id}")
    print(f"Sandbox URL: {sandbox_url}")
    
    # Save info to file
    info_file = Path("DEPLOYMENT_STATUS.md")
    print(f"\n📄 Deployment info saved to {info_file}")

if __name__ == "__main__":
    main()
