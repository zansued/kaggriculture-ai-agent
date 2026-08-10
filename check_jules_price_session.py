"""Monitor Jules session status for the price-aware crop selection task."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.jules_helper import get_session, list_activities

SESSION_ID = "13550014898435574180"

try:
    s = get_session(SESSION_ID)
    state = s.get("state")
    url = s.get("url", "N/A")
    title = s.get("title", "N/A")

    print(f"State: {state}")
    print(f"Title: {title}")
    print(f"URL: {url}")

    try:
        acts = list_activities(SESSION_ID)
        print(f"Activities: {len(acts)}")
        if acts:
            last = acts[-1]
            print(f"Last activity kind: {last.get('kind') or last.get('activityType')}")
            msg = last.get('text') or last.get('message') or last.get('summary') or ''
            if msg:
                print(f"Last activity text: {str(msg)[:200]}")
    except Exception as e:
        print(f"(could not fetch activities: {e})")

    if state in ("COMPLETED", "FAILED", "PAUSED"):
        print(f"SESSION_TERMINAL: {state}")
        sys.exit(0)
    else:
        print("SESSION_ACTIVE")
        sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(2)
