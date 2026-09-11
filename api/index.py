import sys
from pathlib import Path

# Add project root directory to sys.path for serverless runtime
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from main import app as original_app


class VercelPathMiddleware:
    """
    Middleware that restores the original request path on Vercel.
    When Vercel rewrites requests via `vercel.json` to `/api/index.py`,
    it sets the ASGI scope path to `/api/index.py` and sends the real URL
    in the `x-matched-path` header. This middleware restores the true path
    so FastAPI routes (/cashier, /scanner, /, etc.) match perfectly.
    """
    def __init__(self, inner_app):
        self.inner_app = inner_app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            headers = dict(scope.get("headers", []))
            matched = headers.get(b"x-matched-path")
            if matched:
                path = matched.decode("utf-8").split("?")[0]
                scope["path"] = path
                scope["raw_path"] = path.encode("utf-8")
            elif scope.get("path", "").startswith("/api/index.py"):
                new_path = scope["path"][len("/api/index.py"):]
                if not new_path:
                    new_path = "/"
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode("utf-8")
        return await self.inner_app(scope, receive, send)


app = VercelPathMiddleware(original_app)
