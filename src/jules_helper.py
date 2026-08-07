"""
Jules API integration helper for the Kaggriculture agent project.

This module provides a Python interface to the Google Jules coding agent API,
allowing us to programmatically dispatch coding tasks to improve the agent.

Reference: https://jules.google/docs/api/reference/
"""

import os
import json
import requests
from typing import Dict, Any, List, Optional

# Jules API endpoint
JULES_BASE_URL = "https://jules.googleapis.com/v1alpha"
DEFAULT_KEY_PATH = os.path.expanduser("~/.jules/key")


def get_api_key() -> str:
    """Get the Jules API key from environment or local file."""
    key = os.environ.get("JULES_API_KEY", "")
    if key:
        return key

    # Try reading from local key file
    try:
        with open(DEFAULT_KEY_PATH, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    except FileNotFoundError:
        pass

    raise ValueError(
        "Jules API key not found. Set JULES_API_KEY env var or write key to "
        f"{DEFAULT_KEY_PATH}"
    )


def _headers() -> Dict[str, str]:
    """Build request headers with API key."""
    return {"X-Goog-Api-Key": get_api_key()}


def save_api_key(key: str, path: str = DEFAULT_KEY_PATH) -> str:
    """Persist the Jules API key to a local file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(key.strip())
    return path


def list_sources() -> List[Dict[str, Any]]:
    """List all sources (repos) connected to Jules."""
    r = requests.get(f"{JULES_BASE_URL}/sources", headers=_headers())
    r.raise_for_status()
    return r.json().get("sources", [])


def get_source(source_name: str) -> Dict[str, Any]:
    """Get a specific source by name (e.g. 'sources/github/zansued/repo')."""
    r = requests.get(f"{JULES_BASE_URL}/sources/{source_name}", headers=_headers())
    r.raise_for_status()
    return r.json()


def create_session(
    prompt: str,
    source_name: str,
    branch: str = "main",
    title: Optional[str] = None,
    require_plan_approval: bool = False,
    automation_mode: str = "AUTO_CREATE_PR",
) -> Dict[str, Any]:
    """
    Create a new Jules coding session.

    Args:
        prompt: Task description for Jules to execute.
        source_name: Source repo name (e.g. 'sources/github/zansued/kaggriculture-ai-agent').
        branch: Starting branch for the session.
        title: Optional session title.
        require_plan_approval: If True, plans require explicit approval.
        automation_mode: 'AUTO_CREATE_PR' or None.

    Returns:
        Session object from the API.
    """
    payload: Dict[str, Any] = {
        "prompt": prompt,
        "sourceContext": {
            "source": source_name,
            "githubRepoContext": {"startingBranch": branch},
        },
    }
    if title:
        payload["title"] = title
    if require_plan_approval:
        payload["requirePlanApproval"] = True
    if automation_mode:
        payload["automationMode"] = automation_mode

    r = requests.post(
        f"{JULES_BASE_URL}/sessions",
        headers=_headers(),
        json=payload,
    )
    r.raise_for_status()
    return r.json()


def list_sessions(page_size: int = 10) -> List[Dict[str, Any]]:
    """List recent Jules sessions."""
    r = requests.get(
        f"{JULES_BASE_URL}/sessions?pageSize={page_size}",
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json().get("sessions", [])


def get_session(session_id: str) -> Dict[str, Any]:
    """Get a single session by ID."""
    r = requests.get(f"{JULES_BASE_URL}/sessions/{session_id}", headers=_headers())
    r.raise_for_status()
    return r.json()


def list_activities(session_id: str, page_size: int = 30) -> List[Dict[str, Any]]:
    """List activities within a session."""
    r = requests.get(
        f"{JULES_BASE_URL}/sessions/{session_id}/activities?pageSize={page_size}",
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json().get("activities", [])


def send_message(session_id: str, prompt: str) -> Dict[str, Any]:
    """Send a message to an active session."""
    r = requests.post(
        f"{JULES_BASE_URL}/sessions/{session_id}:sendMessage",
        headers=_headers(),
        json={"prompt": prompt},
    )
    r.raise_for_status()
    return r.json()


def approve_plan(session_id: str) -> Dict[str, Any]:
    """Approve a pending plan in a session."""
    r = requests.post(
        f"{JULES_BASE_URL}/sessions/{session_id}:approvePlan",
        headers=_headers(),
    )
    r.raise_for_status()
    return r.json()


def create_kaggriculture_improvement_session(
    source_name: str = "sources/github/zansued/kaggriculture-ai-agent",
    branch: str = "main",
) -> Dict[str, Any]:
    """
    Convenience: create a Jules session to improve the Kaggriculture agent.

    The prompt asks Jules to analyze and improve the agent's decision strategy
    for the farming simulation competition.
    """
    prompt = """
You are working on the Kaggriculture competition agent. This is a Kaggle competition
where an autonomous AI agent manages a virtual farm over 720 turns (30 days x 24 turns)
to maximize profit against other agents.

The game mechanics:
- Actions: plant, water, fertilize, harvest crops; buy/feed/care for animals
  (chickens for eggs, cows for milk, sheep for wool); collect fertilizer;
  buy neighboring land quadrants; trade on a dynamic market.
- Market: unlimited seeds/animals at fixed prices. Sell prices move dynamically
  per resource and persist across days. Prices react to supply/demand.
- Farm: 10x10 grid divided into four 5x5 quadrants. Start with one quadrant.
- Win: most coins at end of 30-day season.

Your task:
1. Analyze the current agent code (src/agent.py, src/utils.py, src/train.py).
2. Improve the agent's decision-making strategy to maximize profit. Consider:
   - Crop selection based on market prices and growth time
   - Optimal planting/harvesting schedules
   - When to buy land quadrants
   - When to invest in animals vs crops
   - Market timing (when to sell)
   - Resource allocation (labor/farm hands)
3. Keep the agent interface compatible: def agent(observation, configuration) -> action.
4. The final submission needs main.py at the root that is self-contained.
5. Add unit tests to tests/.
6. Do NOT submit to Kaggle. Only improve the code and ensure it runs locally
   with `python -c "from src.agent import kaggriculture_agent; print('ok')"`.
7. Preserve the existing project structure.

Important: focus on practical improvements that increase in-game profit.
If the kaggle-environments package is available, test locally. Otherwise,
reason about the game mechanics carefully.
"""

    return create_session(
        prompt=prompt,
        source_name=source_name,
        branch=branch,
        title="Improve Kaggriculture agent strategy",
        automation_mode="AUTO_CREATE_PR",
    )


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "save-key":
        key = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("JULES_API_KEY", "")
        if key:
            path = save_api_key(key)
            print(f"Key saved to {path}")
        else:
            print("ERROR: No key provided. Usage: python jules_helper.py save-key YOUR_KEY")
        sys.exit(0)

    # Default: list sources and print repo availability
    print("=== JULES API HELPER ===")
    try:
        key_path = save_api_key(os.environ.get("JULES_API_KEY", "")) if os.environ.get("JULES_API_KEY") else None
        if key_path:
            print(f"Key saved to {key_path}")

        sources = list_sources()
        print(f"\nConnected sources: {len(sources)}")
        kaggri = [s for s in sources if 'kaggriculture' in s.get('name', '')]
        if kaggri:
            print(f"Kaggriculture repo CONNECTED: {kaggri[0]['name']}")
        else:
            print("WARNING: kaggriculture repo not found in connected sources!")
    except Exception as e:
        print(f"ERROR: {e}")
        print("\nUsage:")
        print("  python jules_helper.py save-key YOUR_API_KEY")
        print("  python -c \"from src.jules_helper import create_kaggriculture_improvement_session; ...\"")
