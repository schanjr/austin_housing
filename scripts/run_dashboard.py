"""
Script to run the Streamlit dashboard directly.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
DASHBOARD_PATH = ROOT_DIR / "app" / "dashboard.py"

def run_dashboard():
    """Run the Streamlit dashboard using Poetry."""
    if not DASHBOARD_PATH.exists():
        print(f"Dashboard file not found at {DASHBOARD_PATH}")
        return
    
    print(f"Starting Streamlit dashboard from {DASHBOARD_PATH}")
    print("To view the dashboard, open your browser and go to http://localhost:8501")
    print("Press Ctrl+C to stop the dashboard")
    
    # Use Poetry to run Streamlit
    poetry_path = "/Users/schan/.pyenv/shims/poetry"
    streamlit_cmd = f"{poetry_path} run streamlit run {DASHBOARD_PATH}"
    os.system(streamlit_cmd)

def main():
    """Main entry point for poetry script."""
    run_dashboard()

if __name__ == "__main__":
    main()
