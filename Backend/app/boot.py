# Backend/app/bootstrap_env.py
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# load the first .env found walking up from CWD or this file
load_dotenv(find_dotenv(usecwd=True), override=True)

# also try repo-root relative to this file (works even if CWD is Backend/)
repo_root_env = Path(__file__).resolve().parents[2] / ".env"
if repo_root_env.exists():
    load_dotenv(repo_root_env, override=True)
