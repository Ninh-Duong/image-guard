"""
server.py - Root HTTP server runner.
Delegates to api/server.py.
"""
import sys
from api.server import run_server

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port)
