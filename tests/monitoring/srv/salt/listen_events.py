import time

import salt.config
import salt.utils.event

opts = salt.config.client_config("/etc/salt/master")
event = salt.utils.event.get_event("master", opts=opts, listen=True)

print("Listening for events (30 seconds)...")
start = time.time()
while time.time() - start < 30:
    ev = event.get_event(wait=1, full=True)
    if ev:
        print(f"Tag: {ev.get('tag')}")
        # print(f"Data: {ev.get('data')}")
        if (
            "grains" in str(ev.get("tag")).lower()
            or "minion" in str(ev.get("tag")).lower()
        ):
            print(f"DATA: {ev.get('data')}")
