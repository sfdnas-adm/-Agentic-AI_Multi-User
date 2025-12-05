#!/usr/bin/env python3
import logging
import os
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

port = os.environ.get("PORT", "8000")
logger.info("Starting server on port: %s", port)

cmd = ["uvicorn", "review_bot.main:app", "--host", "0.0.0.0", "--port", str(port)]

subprocess.run(cmd, check=True)
