"""Entry point for running opencloudtouch as module."""

import uvicorn

from opencloudtouch.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7777)  # nosec B104
