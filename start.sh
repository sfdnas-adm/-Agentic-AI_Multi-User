#!/bin/bash
echo "Environment PORT: '$PORT'"
if [ -z "$PORT" ]; then
    echo "PORT not set, using 8000"
    PORT=8000
else
    echo "Using PORT: $PORT"
fi
exec uvicorn review_bot.main:app --host 0.0.0.0 --port $PORT