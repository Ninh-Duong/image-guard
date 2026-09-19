"""
run.py - Universal entrypoint for Image Guard.
Self-bootstraps missing packages, verifies model weights, and launches the server.
"""
import sys
from bootstrap import ensure_environment

if __name__ == "__main__":
    # 1. Self-bootstrap environment (checks dependencies and model)
    ensure_environment()

    # 2. Import and start server after dependencies are verified
    from server import run_server

    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    run_server(port)
