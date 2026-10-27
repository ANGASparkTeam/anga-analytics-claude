import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ga4_mcp.ratelimit import RegisterRateLimit, SlidingWindow, limits_from_env


def _app(**limits):
    ok = lambda request: PlainTextResponse("ok")  # noqa: E731
    routes = [Route("/register", ok, methods=["POST", "GET"]), Route("/mcp", ok, methods=["POST"])]
    return Starlette(routes=routes, middleware=[Middleware(RegisterRateLimit, **limits)])


def test_sliding_window_expires():
    w = SlidingWindow(2, 10)
    assert w.allow("a", 0) and w.allow("a", 1)
    assert not w.allow("a", 2)
    assert w.allow("b", 2)
    assert w.allow("a", 10.5)


def test_register_limited_per_ip_other_paths_untouched():
    client = TestClient(_app(per_ip=2, total=100))
    assert [client.post("/register").status_code for _ in range(3)] == [200, 200, 429]
    r = client.post("/register")
    assert r.status_code == 429 and r.json()["error"] == "too_many_requests"
    assert r.headers["retry-after"] == "600"
    assert client.get("/register").status_code == 200  # only POST counts
    assert all(client.post("/mcp").status_code == 200 for _ in range(5))


def test_total_cap_across_ips():
    app = _app(per_ip=100, total=1)
    assert TestClient(app, client=("1.1.1.1", 1)).post("/register").status_code == 200
    assert TestClient(app, client=("2.2.2.2", 1)).post("/register").status_code == 429


def test_limits_from_env():
    assert limits_from_env({}) == {"per_ip": 60, "total": 300}
    assert limits_from_env({"REGISTER_LIMIT_PER_IP_HOUR": "3"})["per_ip"] == 3
