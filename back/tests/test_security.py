import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.controllers.auth_controller import router as auth_router
from app.core import security
from app.core.rate_limit import FailedAttemptLimiter


def _request(path: str = "/api/cameras", headers: dict[str, str] | None = None) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": path, "headers": raw_headers, "query_string": b""})


class SecurityTests(unittest.TestCase):
    def test_without_configured_token_everything_passes(self):
        with patch.object(security, "API_TOKEN", None):
            self.assertFalse(security.auth_required())
            self.assertTrue(security.authorized(_request()))

    def test_rejects_missing_or_wrong_token(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            for headers in ({}, {"Authorization": "Bearer errado"}, {"Cookie": f"{security.SESSION_COOKIE}=errado"}):
                self.assertFalse(security.authorized(_request(headers=headers)))

    def test_accepts_bearer_header_and_session_cookie(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            self.assertTrue(security.authorized(_request(headers={"Authorization": "Bearer segredo"})))
            self.assertTrue(security.authorized(_request(headers={"Cookie": f"{security.SESSION_COOKIE}=segredo"})))

    def test_only_session_endpoint_and_non_api_paths_are_public(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            for path in ("/", "/assets/app.js", "/api/session", "/api/session/"):
                self.assertTrue(security.authorized(_request(path)), path)
            for path in ("/api/cameras", "/api/docs", "/api/openapi.json", "/api/rota-futura"):
                self.assertFalse(security.authorized(_request(path)), path)

    def test_local_hosts_are_always_allowed(self):
        for host in ("127.0.0.1", "localhost"):
            self.assertIn(host, security.ALLOWED_HOSTS)


class AccessControlEndToEndTests(unittest.TestCase):
    def _client(self) -> TestClient:
        app = FastAPI(docs_url="/api/docs", openapi_url="/api/openapi.json")
        security.install_access_control(app)
        app.include_router(auth_router)

        @app.get("/api/protegido")
        def protegido() -> dict[str, bool]:
            return {"ok": True}

        @app.get("/")
        def raiz() -> dict[str, bool]:
            return {"spa": True}

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

    def test_docs_schema_and_unknown_api_paths_require_session(self):
        with patch.object(security, "API_TOKEN", "segredo"):
            client = self._client()
            for path in ("/api/docs", "/api/openapi.json", "/api/nao-existe"):
                self.assertEqual(client.get(path).status_code, 401, path)
            self.assertEqual(client.get("/").status_code, 200)
            bearer = {"Authorization": "Bearer segredo"}
            self.assertEqual(client.get("/api/openapi.json", headers=bearer).status_code, 200)
            self.assertEqual(client.get("/api/nao-existe", headers=bearer).status_code, 404)

    def test_foreign_host_header_is_rejected(self):
        with patch.object(security, "API_TOKEN", None):
            client = self._client()
            self.assertEqual(client.get("/api/session").status_code, 200)
            self.assertEqual(client.get("/api/session", headers={"Host": "evil.example"}).status_code, 400)


class BruteForceProtectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = 1000.0
        self.limiter = FailedAttemptLimiter(max_failures=3, window_seconds=60, lock_seconds=30, clock=lambda: self.now)

    def _client(self) -> TestClient:
        app = FastAPI()
        security.install_access_control(app)
        app.include_router(auth_router)

        @app.get("/api/protegido")
        def protegido() -> dict[str, bool]:
            return {"ok": True}

        return TestClient(app)

    def test_wrong_bearer_tokens_lock_the_origin_even_for_the_right_token(self):
        with patch.object(security, "API_TOKEN", "segredo"), patch.object(security, "LIMITER", self.limiter):
            client = self._client()
            for _ in range(3):
                self.assertEqual(client.get("/api/protegido", headers={"Authorization": "Bearer errado"}).status_code, 401)
            blocked = client.get("/api/protegido", headers={"Authorization": "Bearer segredo"})
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers["retry-after"], "30")
            self.assertEqual(client.post("/api/session", json={"token": "segredo"}).status_code, 429)
            self.now += 31
            self.assertEqual(client.get("/api/protegido", headers={"Authorization": "Bearer segredo"}).status_code, 200)

    def test_wrong_session_tokens_count_and_success_resets(self):
        with patch.object(security, "API_TOKEN", "segredo"), patch.object(security, "LIMITER", self.limiter):
            client = self._client()
            for _ in range(2):
                self.assertEqual(client.post("/api/session", json={"token": "errado"}).status_code, 401)
            self.assertEqual(client.post("/api/session", json={"token": "segredo"}).status_code, 200)
            for _ in range(2):
                self.assertEqual(client.post("/api/session", json={"token": "errado"}).status_code, 401)
            self.assertEqual(client.get("/api/protegido").status_code, 200)

    def test_public_paths_are_never_counted_or_blocked_without_token(self):
        with patch.object(security, "API_TOKEN", None), patch.object(security, "LIMITER", self.limiter):
            client = self._client()
            for _ in range(5):
                self.assertEqual(client.get("/api/protegido").status_code, 200)
            self.assertEqual(self.limiter.seconds_locked("testclient"), 0.0)


if __name__ == "__main__":
    unittest.main()
