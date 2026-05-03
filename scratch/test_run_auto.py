import os
from backend.app.database import create_user_database
from backend.app.auto_mode.master_agent import run_auto

create_user_database("rbtrry")

fallback_chain = [{
    "id": 1,
    "provider": "google",
    "model_id": "gemini-3-flash-preview",
    "api_url": "https://generativelanguage.googleapis.com/v1beta",
    "api_keys": ["GOOGLE_API_KEY"],
    "intelligence_rank": 10,
    "display_name": "Gemini Test"
}]

res = run_auto(
    task="Write a python script that prints hello world and save it to test.py",
    env_name="test_env",
    fallback_chain=fallback_chain,
    max_calls=10,
    timeout_secs=60,
    db_name="agentground_rbtrry",
    username="rbtrry",
    log_fn=print
)
print("Result:", res)
