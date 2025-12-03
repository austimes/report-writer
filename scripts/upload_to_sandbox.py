#!/usr/bin/env python3
"""Upload and deploy the FastAPI app to Daytona sandbox using SDK."""

import os
import sys
from pathlib import Path

try:
    from daytona_sdk import Daytona
except ImportError:
    print("❌ daytona-sdk not installed. Install with: uv add daytona-sdk")
    sys.exit(1)

def main():
    print("🚀 Uploading Python app to Daytona sandbox...")
    
    sandbox_id = "522d53be-36b3-4273-835d-188a443cee23"
    convex_url = "https://agreeable-giraffe-398.convex.cloud"
    
    # Get API key from environment
    api_key = os.getenv("DAYTONA_API_KEY")
    if not api_key:
        print("❌ DAYTONA_API_KEY environment variable not set")
        print("Please create an API key at https://daytona.io and set it:")
        print("  export DAYTONA_API_KEY='your-api-key'")
        sys.exit(1)
    
    # Initialize Daytona client
    daytona = Daytona(api_key=api_key)
    
    print(f"Connecting to sandbox: {sandbox_id}")
    sandbox = daytona.sandbox.get(sandbox_id)
    
    # Upload files
    print("📤 Uploading application files...")
    
    base_path = Path("apps/sandbox")
    
    # Create app directory
    print("  Creating /app directory...")
    sandbox.process.execute("mkdir -p /app")
    
    # Upload source code
    print("  Uploading source code...")
    sandbox.fs.upload_directory(str(base_path / "src"), "/app/src")
    
    # Upload project config
    print("  Uploading pyproject.toml...")
    sandbox.fs.upload_file(str(base_path / "pyproject.toml"), "/app/pyproject.toml")
    
    # Upload requirements
    print("  Uploading requirements.lock...")
    sandbox.fs.upload_file(str(base_path / "requirements.lock"), "/app/requirements.lock")
    
    # Install dependencies
    print("\n📦 Installing dependencies...")
    result = sandbox.process.execute("cd /app && uv sync --frozen")
    print(result.stdout)
    if result.exit_code != 0:
        print(f"❌ Failed to install dependencies: {result.stderr}")
        sys.exit(1)
    
    # Install package
    print("\n📦 Installing package...")
    result = sandbox.process.execute("cd /app && uv sync")
    print(result.stdout)
    if result.exit_code != 0:
        print(f"❌ Failed to install package: {result.stderr}")
        sys.exit(1)
    
    # Set environment variables
    print("\n🔧 Setting environment variables...")
    result = sandbox.process.execute(f'export CONVEX_URL="{convex_url}"')
    result = sandbox.process.execute('export PORT=8000')
    
    # Start the server in background
    print("\n🚀 Starting FastAPI server...")
    result = sandbox.process.start_background(
        "cd /app && uvicorn sandbox.main:app --host 0.0.0.0 --port 8000"
    )
    
    print("\n" + "="*60)
    print("✅ Deployment complete!")
    print("="*60)
    print(f"\nAPI URL: https://8000-{sandbox_id}.proxy.daytona.works")
    print(f"Health check: https://8000-{sandbox_id}.proxy.daytona.works/health")
    print("\nTo view logs:")
    print(f"  python3 -c \"from daytona_sdk import Daytona; s=Daytona().sandbox.get('{sandbox_id}'); print(s.logs())\"")

if __name__ == "__main__":
    main()
