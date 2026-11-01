import json
from pathlib import Path

import httpx
import pytest
from mcp import Client

from quera_mcp import http
from quera_mcp.server import mcp

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def page(name: str):
    """Route handler serving a saved HTML page."""
    body = (FIXTURES / name).read_text(encoding="utf-8")
    return lambda request: httpx.Response(200, text=body)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def fresh_http_client(monkeypatch):
    """The shared httpx client is bound to one event loop; each test gets a new loop."""
    monkeypatch.setattr(http, "RETRY_DELAY", 0)
    monkeypatch.setattr(http, "JITTER", (0, 0))
    http.set_transport(None)
    yield
    http.set_transport(None)


@pytest.fixture
def api():
    """Fake quera.org: api["magnet/jobs"] = pageProps dict (served under the Next.js data route), or a callable.

    "/contest" serves the HTML page the build id is read from. Unknown paths return 404 {}.
    Every request is appended to api.calls so tests can assert on query params.
    """

    class Routes(dict):
        calls: list[httpx.Request]

    routes = Routes()
    routes.calls = []
    prefix = "/_next/data/BUILD1/fa/"

    def handler(request: httpx.Request) -> httpx.Response:
        routes.calls.append(request)
        path = request.url.path
        if path == "/contest":
            return httpx.Response(200, text='<html>{"buildId":"BUILD1","x":1}</html>')
        if path.startswith("/blog/wp-json/wp/v2/"):  # the blog's WordPress API: routes["wp/posts"] = JSON body
            target = routes.get("wp/" + path.rsplit("/", 1)[-1])
            if target is None:
                return httpx.Response(404, json={})
            return target(request) if callable(target) else httpx.Response(200, json=target)
        key = path.removeprefix(prefix).removesuffix(".json") if path.startswith(prefix) else None
        target = routes.get(key)
        if target is None:
            return httpx.Response(404, json={})
        if callable(target):
            return target(request)
        return httpx.Response(200, json={"pageProps": target})

    http.set_transport(httpx.MockTransport(handler))
    return routes


@pytest.fixture
async def client():
    async with Client(mcp, raise_exceptions=True) as c:
        call_tool = c.call_tool

        async def parsed(*args, **kwargs):
            result = await call_tool(*args, **kwargs)
            if not result.is_error:
                result.structured_content = json.loads(result.content[0].text)
            return result

        c.call_tool = parsed
        yield c
