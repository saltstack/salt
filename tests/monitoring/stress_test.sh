#!/bin/bash
# Aggressive Salt Master Stress Test

echo "Starting aggressive stress test..."

# 1. Start Event Flooder in the background on the master
echo "Launching event flooder..."
docker exec -d salt-master python3 /srv/salt/flood_events.py

# 2. Loop Highstates on all minions
echo "Starting Highstate loop..."
(
    while true; do
        echo "[$(date)] Running Highstate..."
        docker exec salt-master salt '*' state.highstate --timeout=120 --async
        sleep 10
    done
) &

# 3. Loop various executions (Wheel, Runner, and Local)
echo "Starting Execution loops..."
(
    while true; do
        # Stress the runner system
        docker exec salt-master salt-run manage.status --async
        # Stress the wheel system
        docker exec salt-master salt-key -L
        # Rapid fire pings
        docker exec salt-master salt '*' test.ping --timeout=5
        # Large data returns
        docker exec salt-master salt '*' grains.items --async
        sleep 2
    done
) &

# 4. Stress the file server
(
    while true; do
        docker exec salt-master salt '*' cp.cache_file salt://heavy/heavy_template.jinja
        sleep 5
    done
) &

# 5. Stress the Salt API
(
    while true; do
        ./stress_api.sh
        sleep 1
    done
) &

# 6. Deploy and Remove software in a loop
(
    # First update apt on all minions once
    docker exec salt-master salt '*' pkg.refresh_db
    while true; do
        echo "[$(date)] Deploying software and infra..."
        docker exec salt-master salt '*' state.apply heavy.software_install,webserver,loadbalancer --timeout=300
        sleep 5
        echo "[$(date)] Removing software (keeping infra)..."
        docker exec salt-master salt '*' state.apply heavy.software_remove --timeout=300
        sleep 5
    done
) &

echo "Stress test is running in the background."
echo "Monitor memory at http://localhost:19090 or http://localhost:13000"
echo "To stop: kill all background jobs of this script."

wait
