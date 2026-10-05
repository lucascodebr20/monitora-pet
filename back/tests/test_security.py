import unittest
from unittest.mock import patch

from starlette.requests import Request

from app.core import security


def _request(headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/api/cameras", "headers": raw_headers, "query_string": b""})


class SecurityTests(unittest.TestCase):
    def test_without_configured_token_everything_passes(self):
        with patch.object(security, "API_TOKEN", None):
            self.assertFalse(security.auth_required())
            security.require_session(_request())

    def test_rejects_missing_or_wrong_token(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            for headers in ({}, {"Authorization": "Bearer errado"}, {"Cookie": f"{security.SESSION_COOKIE}=errado"}):
                with self.assertRaises(Exception) as context:
                    security.require_session(_request(headers))
                self.assertEqual(context.exception.status_code, 401)

    def test_accepts_bearer_header_and_session_cookie(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            security.require_session(_request({"Authorization": "Bearer segredo"}))
            security.require_session(_request({"Cookie": f"{security.SESSION_COOKIE}=segredo"}))

    def test_local_hosts_are_always_allowed(self):
        for host in ("127.0.0.1", "localhost"):
            self.assertIn(host, security.ALLOWED_HOSTS)


try:
    import httpx  # noqa: F401

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@unittest.skipUnless(HAS_HTTPX, "httpx é necessário para o TestClient")
class SessionEndpointTests(unittest.TestCase):
    def _client(self):
        from fastapi import Depends, FastAPI
        from fastapi.testclient import TestClient
        from starlette.middleware.trustedhost import TrustedHostMiddleware

        from app.controllers.auth_controller import router

        app = FastAPI()
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=security.ALLOWED_HOSTS)
        app.include_router(router)

        @app.get("/api/protegido", dependencies=[Depends(security.require_session)])
        def protegido() -> dict[str, bool]:
            return {"ok": True}

        return TestClient(app)

    def test_session_cookie_unlocks_protected_routes(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            client = self._client()
            self.assertEqual(client.get("/api/protegido").status_code, 401)
            self.assertEqual(client.get("/api/session").json(), {"required": True, "authenticated": False})

            self.assertEqual(client.post("/api/session", json={"token": "errado"}).status_code, 401)
            opened = client.post("/api/session", json={"token": "segredo"})
            self.assertEqual(opened.status_code, 200)
            cookie = opened.headers["set-cookie"].lower()
            self.assertIn("httponly", cookie)
            self.assertIn("samesite=strict", cookie)

            self.assertEqual(client.get("/api/protegido").json(), {"ok": True})
            self.assertEqual(client.get("/api/session").json(), {"required": True, "authenticated": True})

            client.delete("/api/session")
            self.assertEqual(client.get("/api/protegido").status_code, 401)

    def test_foreign_host_header_is_rejected(self):
        with patch.object(security, "API_TOKEN", None):
            client = self._client()
            self.assertEqual(client.get("/api/session").status_code, 200)
            self.assertEqual(client.get("/api/session", headers={"Host": "evil.example"}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
