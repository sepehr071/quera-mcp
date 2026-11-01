import pytest

pytestmark = [pytest.mark.live, pytest.mark.anyio]


async def test_live_jobs_and_job(client):
    r = (await client.call_tool("qr_jobs", {"level": ["junior"], "order": "new"})).structured_content
    assert r["total"] > 0 and all(j["level"] == "Junior" for j in r["results"])
    job = (await client.call_tool("qr_job", {"id": r["results"][0]["id"]})).structured_content
    assert job["title"] == r["results"][0]["title"] and job["description"]


async def test_live_jobs_search_and_remote(client):
    r = (await client.call_tool("qr_jobs", {"search": "django"})).structured_content
    assert r["total"] >= 1
    r = (await client.call_tool("qr_jobs", {"remote": True})).structured_content
    assert all(j["remote"] for j in r["results"])


async def test_live_companies(client):
    r = (await client.call_tool("qr_companies", {"search": "کایا"})).structured_content
    assert any(c["slug"] == "kaya" for c in r["results"])
    c = (await client.call_tool("qr_company", {"slug": "kaya"})).structured_content
    assert c["name"] and c["website"]


async def test_live_filters(client):
    r = (await client.call_tool("qr_job_filters", {})).structured_content
    assert "118" in r["city"] and r["total_companies"] > 1000


async def test_live_contests(client):
    r = (await client.call_tool("qr_contests", {})).structured_content
    assert r["recently_finished"] and r["topics"]["algorithm"] > 0
    a = (
        await client.call_tool("qr_contests", {"category": "algorithm", "contest_type": "featured"})
    ).structured_content
    assert a["total"] > 10 and len(a["results"]) == 10


async def test_live_problems(client):
    r = (await client.call_tool("qr_problems", {"search": "فاکتوریل"})).structured_content
    assert r["total"] >= 1
    p = (await client.call_tool("qr_problem", {"id": "589"})).structured_content
    assert p["name"] == "فاکتوریل" and p["solved"] > 1000 and "Python 3.12" in p["languages"]


async def test_live_courses(client):
    r = (await client.call_tool("qr_courses", {"search": "پایتون"})).structured_content
    assert r["total"] >= 1 and all(c["price_toman"] >= 0 for c in r["results"])


async def test_live_bootcamps(client):
    r = (await client.call_tool("qr_bootcamps", {})).structured_content
    assert r["total"] >= 1 and all(b["registration_open"] for b in r["results"])
    d = (await client.call_tool("qr_bootcamps", {"slug": r["results"][0]["slug"]})).structured_content
    assert d["price_toman"] and d["syllabus"]


async def test_live_blog(client):
    r = (await client.call_tool("qr_blog", {"category": "python"})).structured_content
    assert len(r["results"]) == 10
    p = (await client.call_tool("qr_blog", {"slug": r["results"][0]["slug"]})).structured_content
    assert p["text"] and p["title"] == r["results"][0]["title"]


async def test_live_event_salaries_filters(client):
    e = (await client.call_tool("qr_event", {"slug": "codecup8-algorithm"})).structured_content
    assert e["participants"] > 1000 and e["prizes"]
    s = (await client.call_tool("qr_salaries", {})).structured_content
    assert s["jobs_total"] >= s["jobs_with_salary"]
    f = (await client.call_tool("qr_problem_filters", {})).structured_content
    assert "python" in f["tag"] and f["contest"]
    p = (await client.call_tool("qr_problems", {"contest": next(iter(f["contest"]))})).structured_content
    assert p["total"] >= 1
