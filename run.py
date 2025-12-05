#!/usr/bin/env python3
import os
import subprocess
import sys

port = os.environ.get("PORT", "8000")
print(f"Starting server on port: {port}")

cmd = ["uvicorn", "review_bot.main:app", "--host", "0.0.0.0", "--port", str(port)]

try:
    subprocess.run(cmd, check=True)
except subprocess.CalledProcessError as e:
    print(f"Server failed to start: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    print("Server stopped by user")
    sys.exit(0)
