import httpx
import pytest
from conftest import fixture

from quera_mcp import http

pytestmark = pytest.mark.anyio

TOOLS = {
    "qr_jobs",
    "qr_job",
    "qr_job_filters",
    "qr_companies",
    "qr_company",
    "qr_contests",
    "qr_problems",
    "qr_problem",
    "qr_courses",
    "qr_salaries",
    "qr_problem_filters",
    "qr_event",
    "qr_bootcamps",
    "qr_blog",
}


async def test_all_tools_are_read_only_and_described(client):
    tools = (await client.list_tools()).tools
    assert {t.name for t in tools} == TOOLS
    for t in tools:
        assert t.annotations.read_only_hint is True, t.name
        assert t.title and t.description.splitlines()[0].endswith("."), t.name
        assert "title" not in str(t.input_schema.get("properties", {}).values()), t.name


async def test_jobs_search_passes_filters_and_trims(client, api):
    api["magnet/jobs"] = fixture("jobs.json")
    api["magnet/jobs"]["jobs"]["totalCount"] = 45
    r = (
        await client.call_tool(
            "qr_jobs",
            {
                "search": "django",
                "level": ["junior", "senior"],
                "technologies": ["React", "docker"],
                "page": 2,
                "job_type": "full-time",
            },
        )
    ).structured_content
    q = api.calls[-1].url.params
    assert q["search"] == "django" and q["collaboration_type"] == "full-time" and q["page"] == "2"
    assert api.calls[-1].url.query.count(b"level=") == 2 and q.get_list("level") == ["junior", "senior"]
    assert q.get_list("technologies") == ["reactjs", "docker"]  # react alias
    assert api.calls[-1].headers["x-nextjs-data"] == "1"
    first = r["results"][0]
    assert r["total"] == 45 and r["has_more"] is True and first["url"] == f"https://quera.org/magnet/jobs/{first['id']}"
    assert set(first) >= {"title", "company", "city", "level", "type", "technologies"} and "logo" not in first


async def test_jobs_remote_filters_client_side(client, api):
    page = fixture("jobs.json")
    page["jobs"]["totalCount"] = 3
    api["magnet/jobs"] = page
    r = (await client.call_tool("qr_jobs", {"remote": True})).structured_content
    flags = [e["node"]["offers_remote"] for e in page["jobs"]["edges"]]
    assert r["total"] == sum(flags) and all(x["remote"] for x in r["results"])
    assert "offers_remote" not in api.calls[-1].url.params


async def test_jobs_city_name_resolves_to_id(client, api):
    page = fixture("jobs.json")
    page["jobs"]["filterChoices"]["initial"].append(
        {"fieldName": "city", "choices": [{"label": "اصفهان", "value": "57"}]}
    )
    api["magnet/jobs"] = page
    await client.call_tool("qr_jobs", {"city": "اصفهان"})
    assert api.calls[-1].url.params["city"] == "57"
    r = await client.call_tool("qr_jobs", {"city": "نامعلوم"})
    assert r.is_error and "اصفهان" in r.content[0].text


async def test_job_detail(client, api):
    api["magnet/jobs/wxvdk"] = fixture("job.json")
    r = (await client.call_tool("qr_job", {"id": "wxvdk"})).structured_content
    assert api.calls[-1].url.params["pk"] == "wxvdk"
    assert (
        r["company_slug"] == "kaya"
        and r["valid_through"] == "2026-12-18"
        and r["skills"] == ["JavaScript", "Python", "Jira"]
    )
    assert r["salary_toman_month"] == "55,000,000 تا 65,000,000"
    assert "<p" not in r["description"] and r["description"].startswith("About the Role")
    assert r["other_jobs_from_company"][0]["id"] == "7rvmq"


async def test_missing_job_is_a_clear_error(client, api):
    r = await client.call_tool("qr_job", {"id": "zzzzz"})
    assert r.is_error and "404" in r.content[0].text


async def test_companies_and_company(client, api):
    api["magnet/companies"] = fixture("companies.json")
    r = (
        await client.call_tool("qr_companies", {"search": "کایا", "size": "11-50", "technologies": ["python"]})
    ).structured_content
    assert api.calls[-1].url.params["size"] == "11-50" and r["results"][0]["url"].startswith(
        "https://quera.org/magnet/companies/"
    )
    api["magnet/companies/kaya"] = fixture("company.json")
    api["magnet/jobs"] = fixture("company_jobs.json")
    c = (await client.call_tool("qr_company", {"slug": "kaya"})).structured_content
    assert c["name"] == "گروه کایا" and c["website"] == "http://www.kaya.ir" and c["founded_jalali_year"] == 1396
    assert c["open_jobs"] and api.calls[-1].url.params["company"] == "kaya"
    assert "gallery_count" not in c and "<p" not in c["about"]


async def test_contests_overview_and_archive(client, api):
    api["contest"] = fixture("contest.json")
    r = (await client.call_tool("qr_contests", {})).structured_content
    assert r["recently_finished"][0]["url"].startswith("https://quera.org/") and "algorithm" in r["topics"]
    api["contest/search/backend"] = fixture("contest_search.json")
    r = (
        await client.call_tool(
            "qr_contests", {"category": "backend", "contest_type": "featured", "organizer": "digikala"}
        )
    ).structured_content
    assert api.calls[-1].url.params["organizer"] == "digikala" and r["results"] and "total" in r


async def test_problems_and_problem(client, api):
    api["problemset"] = fixture("problems.json")
    r = (
        await client.call_tool("qr_problems", {"tag": "python", "difficulty": "easy", "order": "most-liked"})
    ).structured_content
    q = api.calls[-1].url.params
    assert q["difficulty"] == "EZ" and q["tag"] == "python" and q["order"] == "most-liked"
    assert r["results"][0]["url"].startswith("https://quera.org/problemset/")
    api["problemset/589"] = fixture("problem.json")
    p = (await client.call_tool("qr_problem", {"id": "589"})).structured_content
    assert (
        p["name"] == "فاکتوریل"
        and p["difficulty"] == "easy"
        and "Python 3.12" in p["languages"]
        and "$$" in p["statement"]
    )


async def test_courses(client, api):
    api["college"] = fixture("college.json")
    r = (await client.call_tool("qr_courses", {"search": "پایتون", "level": "advanced"})).structured_content
    q = api.calls[-1].url.params
    assert q["level"] == "2" and q["search"] == "پایتون"
    c = r["results"][0]
    assert c["url"].startswith("https://quera.org/college/landpage/") and isinstance(c["price_toman"], int)
    assert r["upcoming"]


async def test_free_course_uses_visitor_price(client, api):
    page = fixture("college.json")
    page["trackColleges"]["edges"][0]["node"]["college"]["price_info"] = {"price": 1199000, "user_price": 0}
    api["college"] = page
    c = (await client.call_tool("qr_courses", {})).structured_content["results"][0]
    assert c["free"] is True and c["price_toman"] == 1199000 and c["your_price_toman"] == 0


async def test_new_filter_params(client, api):
    api["magnet/jobs"] = fixture("jobs.json")
    await client.call_tool("qr_jobs", {"company_size": "11-50"})
    assert api.calls[-1].url.params["company_size"] == "11-50"
    api["problemset"] = fixture("problems.json")
    await client.call_tool("qr_problems", {"contest": "28542"})
    assert api.calls[-1].url.params["contest"] == "28542"


async def test_salaries_group_by_level(client, api):
    page = fixture("jobs.json")
    page["jobs"]["totalCount"] = 3
    for e, (sal, lv) in zip(
        page["jobs"]["edges"],
        [("۵۵,۰۰۰,۰۰۰ تا ۶۵,۰۰۰,۰۰۰", "Junior"), ("۳۵,۰۰۰,۰۰۰ تا ۴۵,۰۰۰,۰۰۰", "Junior"), (None, "Senior")],
        strict=True,
    ):
        e["node"]["salary"], e["node"]["level"] = sal, lv
    api["magnet/jobs"] = page
    r = (await client.call_tool("qr_salaries", {})).structured_content
    assert r["jobs_total"] == 3 and r["jobs_with_salary"] == 2 and list(r["by_level"]) == ["Junior"]
    assert r["by_level"]["Junior"] == {
        "jobs": 2,
        "lowest_toman": 35_000_000,
        "median_toman": 50_000_000,
        "highest_toman": 65_000_000,
    }


async def test_problem_filters(client, api):
    api["problemset"] = fixture("problem_filters.json")
    r = (await client.call_tool("qr_problem_filters", {})).structured_content
    assert r["tag"] and r["contest"] and r["type"]["J"] and "difficulty" not in r


async def test_event(client, api):
    api["events/codecup8-algorithm"] = fixture("event.json")
    r = (await client.call_tool("qr_event", {"slug": "codecup8-algorithm"})).structured_content
    assert r["title"] == "کدکاپ ۸" and r["participants"] == 5531 and r["registration_closed"] is True
    assert r["prizes"][0] == {"نفر اول": "۳۰ میلیون تومان"} and r["sub_events"] is not None
    assert r["url"] == "https://quera.org/events/codecup8-algorithm" and "<p" not in r["intro"]


async def test_bootcamps_list_and_detail(client, api):
    api["bootcamp"] = fixture("bootcamps.json")
    r = (await client.call_tool("qr_bootcamps", {})).structured_content
    assert [b["slug"] for b in r["results"]] == ["ai", "devops"]
    devops = next(b for b in r["results"] if b["slug"] == "devops")
    assert devops["price_toman"] == 49_192_000 and devops["starts"] == "2026-11-26" and devops["seats_left"] == 28
    r = (await client.call_tool("qr_bootcamps", {"include_closed": True})).structured_content
    assert r["total"] == 3
    api["bootcamp/devops"] = fixture("bootcamp.json")
    d = (await client.call_tool("qr_bootcamps", {"slug": "devops"})).structured_content
    assert api.calls[-1].url.params["slug"] == "devops"
    assert d["list_price_toman"] == 55_900_000 and d["price_toman"] == 49_192_000
    assert d["syllabus"][0]["items"] and d["instructors"][0]["name"] and d["duration"] == "13 هفته, 288 ساعت"


async def test_blog_list_post_and_category(client, api):
    api["wp/categories"] = fixture("wp_categories.json")
    api["wp/posts"] = fixture("wp_posts.json")
    r = (await client.call_tool("qr_blog", {"search": "python", "category": "python"})).structured_content
    q = api.calls[-1].url.params
    assert q["search"] == "python" and q["categories"] == "64" and q["per_page"] == "10"
    assert r["results"][0]["url"].startswith("https://quera.org/blog/") and "<" not in r["results"][0]["excerpt"]
    assert r["results"][0]["categories"]
    post = {**fixture("wp_posts.json")[0], "content": {"rendered": "<p>متن &amp; بدنه</p>"}}
    api["wp/posts"] = [post]
    p = (await client.call_tool("qr_blog", {"slug": post["slug"]})).structured_content
    assert p["text"] == "متن & بدنه" and api.calls[-1].url.params["slug"] == post["slug"]
    api["wp/posts"] = []
    r = await client.call_tool("qr_blog", {"slug": "zz"})
    assert r.is_error and "No blog post" in r.content[0].text
    r = await client.call_tool("qr_blog", {"category": "nope"})
    assert r.is_error and "Valid:" in r.content[0].text


async def test_filters_tool(client, api):
    api["magnet/jobs"] = fixture("jobs.json")
    api["magnet/companies"] = fixture("companies.json")
    r = (await client.call_tool("qr_job_filters", {})).structured_content
    assert "technologies" in r and "industry" in r and r["total_open_jobs"] >= 1


async def test_stale_build_id_is_refreshed_once(client, api):
    api["magnet/jobs"] = fixture("jobs.json")
    http._build_id = "OLD"
    r = await client.call_tool("qr_jobs", {})
    assert not r.is_error and http._build_id == "BUILD1"


async def test_calls_send_the_headers_chrome_sends_for_data_and_page(client, api):
    api["magnet/jobs"] = fixture("jobs.json")
    http._build_id = None
    await client.call_tool("qr_jobs", {})
    page, data = api.calls[0].headers, api.calls[1].headers  # build id page first, then the Next.js data route
    assert (page["accept"].startswith("text/html,application/xhtml+xml"), page["sec-fetch-dest"]) == (True, "document")
    assert (page["sec-fetch-mode"], page["sec-fetch-site"], page["priority"]) == ("navigate", "none", "u=0, i")
    assert "referer" not in page
    assert (data["accept"], data["x-nextjs-data"], data["referer"]) == ("*/*", "1", "https://quera.org/")
    assert (data["sec-fetch-mode"], data["sec-fetch-dest"], data["sec-fetch-site"], data["priority"]) == (
        "cors",
        "empty",
        "same-origin",
        "u=1, i",
    )
    assert "origin" not in data and data["accept-language"].startswith("fa-IR")


async def test_foreign_host_refused():
    with pytest.raises(http.ApiError):
        await http._get("https://example.com/x", {}, {})


async def test_digits_and_text_helpers():
    from quera_mcp.quera import _digits, _text

    assert _digits("۵۵٬۰۰۰ تا ۶۵") == "55,000 تا 65"
    assert _text("<p>a&amp;b</p><ul><li>x</li></ul>", 100) == "a&b\nx"
    assert _text("x" * 50, 10).endswith("[truncated]")
    assert httpx.URL("https://quera.org/").host in http.HOSTS
