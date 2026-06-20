#!/bin/bash
# Stress test the Salt API

API_URL="http://localhost:18000"
USER="salt"
PASS="salt"

echo "Starting Salt API stress test..."

# Function to get a token
get_token() {
    curl -s -c /tmp/cookies.txt -H "Accept: application/json" \
        -d username=$USER -d password=$PASS -d eauth=pam \
        $API_URL/login | python3 -c "import sys, json; print(sys.stdin.read())" | grep -oP '"token": "\K[^"]+'
}

TOKEN=$(get_token)
echo "Got token: $TOKEN"

while true; do
    # Run a command via API
    curl -s -H "Accept: application/json" -H "X-Auth-Token: $TOKEN" \
        -d client=local -d tgt='*' -d fun=test.ping \
        $API_URL > /dev/null

    # Run a runner via API
    curl -s -H "Accept: application/json" -H "X-Auth-Token: $TOKEN" \
        -d client=runner -d fun=manage.status \
        $API_URL > /dev/null

    sleep 0.1
done
