"""
Script to run the Streamlit dashboard directly.
Compatible with both local Poetry environment and Streamlit Community Cloud.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DASHBOARD_PATH = ROOT_DIR / "app" / "dashboard.py"

def detect_environment():
    """Detect if we're running in Streamlit Community Cloud or local environment."""
    # Check for Streamlit Community Cloud environment variables or paths
    if (os.getenv('STREAMLIT_SHARING_MODE') or 
        os.getenv('STREAMLIT_SERVER_PORT') or 
        '/mount/src/' in str(Path.cwd()) or
        os.getenv('HOME') == '/home/appuser'):
        return 'streamlit_cloud'
    
    # Check if Poetry is available
    if shutil.which('poetry'):
        return 'local_poetry'
    
    # Check if we're in a virtual environment with streamlit installed
    try:
        import streamlit
        return 'local_direct'
    except ImportError:
        return 'unknown'

def run_dashboard_local_poetry():
    """Run dashboard using Poetry (local development)."""
    print("🚀 Running dashboard with Poetry...")
    
    # Try to find poetry in common locations
    poetry_paths = [
        shutil.which('poetry'),              # System PATH (works in Streamlit Cloud)
        "/Users/schan/.pyenv/shims/poetry",  # User's specific local path
        os.path.expanduser("~/.local/bin/poetry"),  # Common local install
        "/usr/local/bin/poetry",             # Common system install
        "/opt/poetry/bin/poetry",            # Docker/container installs
        "poetry"                             # Just try the command directly
    ]
    
    poetry_path = None
    for path in poetry_paths:
        if path and (path == "poetry" or Path(path).exists()):
            poetry_path = path
            break
    
    if not poetry_path:
        print("❌ Poetry not found. Falling back to direct streamlit execution...")
        return run_dashboard_direct()
    
    try:
        cmd = [poetry_path, "run", "streamlit", "run", str(DASHBOARD_PATH)]
        print(f"🔧 Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Poetry command failed: {e}")
        print("🔄 Falling back to direct streamlit execution...")
        return run_dashboard_direct()
    except FileNotFoundError as e:
        print(f"❌ Poetry executable not found: {e}")
        print("🔄 Falling back to direct streamlit execution...")
        return run_dashboard_direct()

def run_dashboard_direct():
    """Run dashboard directly with streamlit (Streamlit Cloud or fallback)."""
    print("🌐 Running dashboard directly with streamlit...")
    
    # Add the project root to Python path for imports
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    
    try:
        # Try to run streamlit directly
        cmd = ["streamlit", "run", str(DASHBOARD_PATH)]
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Streamlit command failed: {e}")
        return False
    except FileNotFoundError:
        print("❌ Streamlit not found in PATH")
        return False
    
    return True

def run_dashboard_streamlit_cloud():
    """Run dashboard in Streamlit Community Cloud environment."""
    print("☁️ Running in Streamlit Community Cloud environment...")
    
    # In Streamlit Cloud, we don't need to start streamlit - it's already running
    # We just need to ensure the dashboard module can be imported
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    
    # Import and run the dashboard directly
    try:
        sys.path.insert(0, str(ROOT_DIR / "app"))
        import dashboard
        dashboard.main()
    except ImportError as e:
        print(f"❌ Failed to import dashboard: {e}")
        return False
    
    return True

def run_dashboard():
    """Run the Streamlit dashboard with environment detection."""
    if not DASHBOARD_PATH.exists():
        print(f"❌ Dashboard file not found at {DASHBOARD_PATH}")
        return False
    
    environment = detect_environment()
    print(f"🔍 Detected environment: {environment}")
    
    # For Streamlit Cloud, try Poetry first (since it's installed), then fallback
    if environment == 'streamlit_cloud':
        print("☁️ Streamlit Cloud detected - trying Poetry first...")
        # Check if poetry is available in PATH
        if shutil.which('poetry'):
            print("✅ Poetry found in PATH, using Poetry execution...")
            return run_dashboard_local_poetry()
        else:
            print("❌ Poetry not in PATH, using direct execution...")
            return run_dashboard_streamlit_cloud()
    elif environment == 'local_poetry':
        return run_dashboard_local_poetry()
    elif environment == 'local_direct':
        return run_dashboard_direct()
    else:
        print("⚠️ Unknown environment, trying direct streamlit execution...")
        return run_dashboard_direct()

def main():
    """Main entry point for poetry script and direct execution."""
    print("🏠 Austin Housing Dashboard Launcher")
    print("=" * 50)
    
    success = run_dashboard()
    
    if not success:
        print("\n❌ Failed to start dashboard")
        print("💡 Troubleshooting tips:")
        print("   - Ensure streamlit is installed: pip install streamlit")
        print("   - For local development: poetry install && poetry run dashboard")
        print("   - Check that all dependencies are available")
        sys.exit(1)
    else:
        print("✅ Dashboard started successfully!")

if __name__ == "__main__":
    main()
