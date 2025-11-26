#!/usr/bin/env python3
"""
LangGraph Studio Quickstart Script
Loads environment variables and starts LangGraph dev server
"""
import os
import sys
import subprocess
from pathlib import Path

def load_env_file(env_path: Path):
    """Load environment variables from .env file, handling encoding issues"""
    if not env_path.exists():
        return
    
    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'cp949', 'latin-1']
    env_vars = {}
    
    for encoding in encodings:
        try:
            with open(env_path, 'r', encoding=encoding) as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        env_vars[key] = value
            print(f"✓ Loaded .env file with {encoding} encoding")
            break
        except (UnicodeDecodeError, Exception) as e:
            continue
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value

def main():
    # Change to project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    # Load .env file from project root
    env_path = project_root / '.env'
    if env_path.exists():
        print("Loading environment variables from .env file...")
        load_env_file(env_path)
        # Print loaded API key status (masked)
        api_key = os.environ.get('LANGSMITH_API_KEY', '')
        if api_key:
            print(f"✓ LANGSMITH_API_KEY loaded (length: {len(api_key)})")
        else:
            print("⚠ LANGSMITH_API_KEY is empty or not set in .env file")
            print("  Studio will work but LangSmith runs tracking will be disabled")
    
    # Verify API key is loaded from project root .env
    api_key = os.environ.get('LANGSMITH_API_KEY', '')
    project_name = os.environ.get('LANGSMITH_PROJECT', 'CANT')
    if api_key:
        print(f"✓ LANGSMITH_API_KEY loaded from {env_path} (length: {len(api_key)})")
        print(f"✓ LANGSMITH_PROJECT: {project_name}")
    else:
        print("⚠ LANGSMITH_API_KEY is empty or not set in .env file")
        print("  Studio will work but LangSmith runs tracking will be disabled")
    
    # Change to backend directory (LangGraph dev runs from here)
    backend_dir = project_root / 'backend'
    os.chdir(backend_dir)
    
    # Start LangGraph dev server
    print("\n" + "=" * 50)
    print("LangGraph Studio Quickstart")
    print("=" * 50)
    print("\nStarting LangGraph dev server...")
    print("Port: 2024")
    print("\nOpen this URL in your browser:")
    print("https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024")
    print("\nPress Ctrl+C to stop the server.\n")
    
    # Run langgraph dev (browser will open automatically)
    # Pass environment variables to subprocess (from project root .env)
    config_path = project_root / 'langgraph.json'
    env = os.environ.copy()
    # Explicitly set environment variables for LangGraph dev
    env['LANGSMITH_API_KEY'] = api_key
    env['LANGSMITH_PROJECT'] = project_name
    env['LANGSMITH_TRACING_V2'] = os.environ.get('LANGSMITH_TRACING_V2', 'true')
    
    if api_key:
        print(f"🔑 Environment variables set for LangGraph dev:")
        print(f"   LANGSMITH_API_KEY: {'*' * 20}...{api_key[-10:] if len(api_key) > 10 else 'N/A'}")
        print(f"   LANGSMITH_PROJECT: {project_name}\n")
    
    subprocess.run([
        sys.executable, '-m', 'langgraph_cli', 'dev',
        '--host', '127.0.0.1',
        '--port', '2024',
        '--config', str(config_path)
    ], env=env)

if __name__ == '__main__':
    main()

