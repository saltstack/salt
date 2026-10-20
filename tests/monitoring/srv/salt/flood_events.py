import os
import time

import salt.config
import salt.utils.event

# Load master config
opts = salt.config.client_config("/etc/salt/master")
event = salt.utils.event.get_event("master", opts=opts, listen=False)

print(f"Starting event flood from PID {os.getpid()}...")
try:
    count = 0
    while True:
        # Fire events with a 1KB payload
        event.fire_event(
            {"count": count, "payload": "f" * 1024, "timestamp": time.time()},
            "stress/test/flood",
        )
        count += 1
        if count % 1000 == 0:
            print(f"Fired {count} events...")
except KeyboardInterrupt:
    print("Stopped.")
