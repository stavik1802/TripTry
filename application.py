# application.py
from pathlib import Path
import sys

# Make Backend importable
sys.path.insert(0, str(Path(__file__).parent / "Backend"))

# Import and expose the *actual* FastAPI app (keeps mounts & middleware)
from app.server import app as application  # noqa: E402

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(application, host="0.0.0.0", port=8000, reload=True)
