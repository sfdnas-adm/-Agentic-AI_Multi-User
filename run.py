#!/usr/bin/env python3
import os
import subprocess

port = os.environ.get("PORT", "8000")
print(f"Starting server on port: {port}")

cmd = ["uvicorn", "review_bot.main:app", "--host", "0.0.0.0", "--port", str(port)]

subprocess.run(cmd)
