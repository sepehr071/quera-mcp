"""Quera (quera.org) tools: developer jobs and companies (Magnet), contests, problemset, courses (College)."""

from __future__ import annotations

import html
import json
import re
import statistics
from typing import Annotated, Any, Literal

from pydantic import Field

from . import http
from .http import ApiError
from .registry import tool

SITE = http.SITE
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٬", "0123456789,")
LEVELS = {
    "intern": "intern",
    "junior": "junior",
    "mid": "mid-level",
    "mid-level": "mid-level",
    "senior": "senior",
    "lead": "manager",
    "manager": "manager",
}
TECH_ALIASES = {
    "react": "reactjs",
    "node": "node.js",
    "nodejs": "node.js",
    "nextjs": "next.js",
    "vue": "vue.js",
    "vuejs": "vue.js",
    "golang": "go",
    "csharp": "c#",
    "dotnet": ".net",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "ci/cd": "cicd",
}
DIFFICULTY = {"easy": "EZ", "ez": "EZ", "medium": "MED", "med": "MED", "hard": "HARD"}


def _digits(s: str | None) -> str | None:
    return s.translate(_DIGITS) if s else s


def _text(markup: str | None, limit: int) -> str:
    """HTML to plain text, capped at `limit` characters."""
    t = html.unescape(re.sub(r"<(br|/p|/li|/h\d|/ul)[^>]*>", "\n", markup or ""))
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"[ \t\r ]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t).strip()
    return t if len(t) <= limit else t[:limit].rstrip() + " [truncated]"


def _tech(v: str) -> str:
    v = v.strip().lower()
    return TECH_ALIASES.get(v, v)


def _techs(v: str | list[str] | None) -> list[str] | None:
    if not v:
        return None
    return [_tech(x) for x in ([v] if isinstance(v, str) else v)]


def _job(n: dict) -> dict:
    techs = sorted(n.get("jobtechnology_set") or [], key=lambda t: not t["is_main"])
    return {
        "id": n["pk"],
        "title": n["title"],
        "company": (n.get("company") or {}).get("name"),
        "city": (n.get("city") or {}).get("name"),
        "level": n.get("level"),
        "type": n.get("collaboration_type"),
        "remote": n.get("offers_remote"),
        "salary_toman_month": _digits(n.get("salary")),
        "technologies": [t["technology"]["name"] for t in techs],
        "posted": (n.get("publish_time") or "")[:10],
        "url": f"{SITE}/magnet/jobs/{n['pk']}",
    }


def _company(n: dict) -> dict:
    return {
        "slug": n["slug"],
        "name": n["name"],
        "tagline": n.get("tagline"),
        "city": (n.get("city") or {}).get("name"),
        "size": _digits(n.get("size")),
        "open_jobs": n.get("open_job_count"),
        "technologies": [t["name"] for t in (n.get("technologies") or [])][:10],
        "url": f"{SITE}/magnet/companies/{n['slug']}",
    }


def _contest(n: dict) -> dict:
    c = n["contest"]
    slug = n.get("event_slug")
    return {
        "id": c["id"],
        "name": c["name"],
        "type": (c.get("contest_type") or "").lower(),
        "start": n.get("start_time"),
        "finish": n.get("finish_time"),
        "duration": _digits(n.get("duration_display")),
        "participants": n.get("user_cnt"),
        "problems": n.get("problem_cnt"),
        "organizer": n.get("organizer_name"),
        "description": c.get("featured_card_description"),
        "url": f"{SITE}/events/{slug}"
        if slug
        else f"{SITE}/contest/assignments/{n['assignment']['assignment']['pk']}/problems",
    }


def _problem(n: dict) -> dict:
    return {
        "id": n["pk"],
        "name": n["name"],
        "difficulty": (n.get("difficulty") or "").lower(),
        "solved": n.get("solved_count"),
        "tried": n.get("tried_count"),
        "source": (n.get("source") or {}).get("name"),
        "tags": [t["name"] for t in n.get("tags") or []],
        "url": f"{SITE}/problemset/{n['pk']}",
    }


def _course(n: dict) -> dict:
    c, p = n["college"], n["college"].get("price_info") or {}
    return {
        "slug": c["url_name"],
        "name": c["name"],
        "about": c.get("name_description"),
        "level": n["level"]["title"],
        "badge": c.get("tag_text"),
        "price_toman": p.get("price"),
        # user_price is what an anonymous visitor pays (0 = free promotion, the site shows "رایگان")
        "your_price_toman": p.get("user_price"),
        "free": p.get("user_price") == 0,
        "url": f"{SITE}/college/landpage/{c['pk']}/{c['url_name']}",
    }


def _paged(block: dict, items: list, page: int, size: int) -> dict:
    total = block["totalCount"]
    return {"total": total, "page": page, "has_more": page * size < total, "results": items}


async def _city_id(city: str) -> str:
    """City name or id -> the id the site filters by (only cities the site lists are valid)."""
    if city.isdigit():
        return city
    for f in (await http.fetch("magnet/jobs"))["jobs"]["filterChoices"]["initial"]:
        if f["fieldName"] == "city":
            for c in f["choices"]:
                if city.strip() in c["label"]:
                    return c["value"]
            raise ApiError(
                "Unknown city. Cities with jobs filter: " + ", ".join(c["label"] for c in f["choices"]) + "."
            )
    raise ApiError("City filter not found.")


Page = Annotated[int, Field(ge=1, le=100, description="Page number, from 1.")]


@tool("Search Quera jobs")
async def qr_jobs(
    search: Annotated[str | None, Field(description="Words to look for, e.g. 'django', 'devops', 'فرانت'.")] = None,
    level: Annotated[
        list[Literal["intern", "junior", "mid", "senior", "lead"]] | None,
        Field(description="Seniority; several mean any of them."),
    ] = None,
    remote: Annotated[bool | None, Field(description="true = only jobs that offer remote work.")] = None,
    city: Annotated[
        str | None, Field(description="City name (Persian, e.g. 'تهران', 'اصفهان') or id. See qr_job_filters.")
    ] = None,
    technologies: Annotated[
        list[str] | None,
        Field(description="Tech codes such as 'python', 'react', 'docker', 'go'; several mean any of them."),
    ] = None,
    job_type: Annotated[
        Literal["full-time", "part-time", "project-based"] | None, Field(description="Collaboration type.")
    ] = None,
    company: Annotated[str | None, Field(description="Company slug from qr_companies, e.g. 'kaya'.")] = None,
    industry: Annotated[str | None, Field(description="Industry id from qr_job_filters (1 = IT/software).")] = None,
    company_size: Annotated[
        Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10000+"] | None,
        Field(description="Employee count range of the hiring company."),
    ] = None,
    order: Annotated[
        Literal["relevant", "new", "trending", "high_salary"] | None, Field(description="Sort order; default relevant.")
    ] = None,
    page: Page = 1,
) -> dict:
    """Search the open tech jobs on Quera Magnet (Iran's developer job board), 15 per page.

    Use for 'junior Python jobs in Tehran' or 'remote DevOps roles'. Each result has an id: call qr_job for the
    full description. Salary is Toman per month when the employer published it. Filters combine with AND.
    """
    q: dict[str, Any] = {
        "search": search,
        "level": [LEVELS[x] for x in level or []],
        "city": await _city_id(city) if city else None,
        "technologies": _techs(technologies),
        "collaboration_type": job_type,
        "company": company,
        "industry": industry,
        "company_size": company_size,
        "order": order,
        "page": page if page > 1 else None,
    }
    if remote is not None:
        # The site has no remote filter (its offers_remote parameter is ignored), so filter here.
        # shortcut: reads at most 6 pages (90 jobs, more than the board holds); returns all matches, ignores `page`.
        jobs: list[dict] = []
        for n in range(1, 7):
            j = (await http.fetch("magnet/jobs", {**q, "page": n if n > 1 else None}))["jobs"]
            jobs += [_job(e["node"]) for e in j["edges"]]
            if n * 15 >= j["totalCount"]:
                break
        jobs = [x for x in jobs if bool(x["remote"]) == remote]
        return {"total": len(jobs), "page": 1, "has_more": False, "results": jobs}
    j = (await http.fetch("magnet/jobs", q))["jobs"]
    return _paged(j, [_job(e["node"]) for e in j["edges"]], page, 15)


@tool("Get a Quera job")
async def qr_job(id: Annotated[str, Field(description="Job id (5 characters) from qr_jobs, e.g. 'wxvdk'.")]) -> dict:
    """Get one Quera job posting: description, requirements, benefits, skills, salary, deadline and related jobs.

    Call after qr_jobs. Use qr_company with the company slug for the employer's profile.
    """
    j = (await http.fetch(f"magnet/jobs/{id}", {"pk": id}))["job"]
    try:
        ld = json.loads(j.get("schema") or "{}")
    except ValueError:
        ld = {}

    def short(x):
        return {
            "id": x["pk"],
            "title": x["title"],
            "company": x["company"]["name"],
            "city": (x.get("city") or {}).get("name"),
        }

    return {
        **_job(j),
        "company_slug": j["company"]["slug"],
        "company_website": j["company"].get("website"),
        "open": j.get("open"),
        "valid_through": ld.get("validThrough"),
        "apply_url": j.get("apply_at_url") or None,
        "summary": _text(j.get("description_summary"), 400),
        "description": _text(j.get("description"), 3500),
        "requirements": _text(j.get("requirements"), 3500),
        "benefits": ld.get("jobBenefits"),
        "skills": ld.get("skills"),
        "other_jobs_from_company": [short(x) for x in (j.get("other_jobs_from_company") or [])[:5]],
        "similar_jobs": [short(x) for x in (j.get("similar_jobs") or [])[:5]],
    }


@tool("Quera job filter choices")
async def qr_job_filters() -> dict:
    """List the filter values qr_jobs and qr_companies accept: cities, industries, company sizes, popular tech codes and companies.

    Call once when unsure which city, industry id or technology code to use. Any tech code works, not only these.
    """
    p = await http.fetch("magnet/jobs")
    c = await http.fetch("magnet/companies")
    out: dict[str, Any] = {"total_open_jobs": p["jobs"]["totalCount"], "total_companies": c["companies"]["totalCount"]}
    for f in p["jobs"]["filterChoices"]["initial"]:
        if f["fieldName"] in ("order", "level", "collaboration_type"):
            continue
        out[f["fieldName"]] = {x["value"]: _digits(x["label"]) for x in f["choices"]}
    return out


@tool("Search Quera companies")
async def qr_companies(
    search: Annotated[str | None, Field(description="Company name words, Persian or English.")] = None,
    industry: Annotated[str | None, Field(description="Industry id from qr_job_filters.")] = None,
    city: Annotated[str | None, Field(description="City name or id, as for qr_jobs.")] = None,
    technologies: Annotated[list[str] | None, Field(description="Tech codes the company uses, e.g. 'python'.")] = None,
    size: Annotated[
        Literal["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10000+"] | None,
        Field(description="Employee count range."),
    ] = None,
    page: Page = 1,
) -> dict:
    """Search the 3,000+ companies with a Quera Magnet profile, 15 per page.

    Use to find employers by name, city, size or tech stack. open_jobs counts their current postings:
    call qr_company for the profile and its jobs.
    """
    q = {
        "search": search,
        "industry": industry,
        "city": await _city_id(city) if city else None,
        "technologies": _techs(technologies),
        "size": size,
        "page": page if page > 1 else None,
    }
    c = (await http.fetch("magnet/companies", q))["companies"]
    return _paged(c, [_company(e["node"]) for e in c["edges"]], page, 15)


@tool("Get a Quera company")
async def qr_company(
    slug: Annotated[str, Field(description="Company slug from qr_companies or qr_job, e.g. 'kaya'.")],
) -> dict:
    """Get a company's Quera profile (about, size, industry, tech stack, benefits, contacts) and its open jobs.

    Call after qr_companies or qr_job. The jobs list has ids for qr_job.
    """
    c = (await http.fetch(f"magnet/companies/{slug}", {"slug": slug}))["company"]
    jobs = (await http.fetch("magnet/jobs", {"company": slug}))["jobs"]
    return {
        "slug": slug,
        "name": c["name"],
        "tagline": c.get("tagline"),
        "industry": c.get("industry"),
        "size": _digits(c.get("size")),
        "founded_jalali_year": c.get("founded"),
        "city": (c.get("city") or {}).get("name"),
        "address": c.get("address"),
        "website": c.get("website"),
        "social": {s["type"]: s["url"] for s in c.get("socialnetworkpage_set") or []},
        "about": _text(c.get("short_statement"), 1500),
        "statement": _text(c.get("statement"), 1500),
        "technologies": [t["name"] for t in c.get("technologies") or []],
        "benefits": [b["name"] for b in c.get("benefit_set") or []],
        "open_jobs": [_job(e["node"]) for e in jobs["edges"]],
        "url": f"{SITE}/magnet/companies/{slug}",
    }


@tool("Quera contests")
async def qr_contests(
    category: Annotated[
        Literal["algorithm", "backend", "frontend", "ai", "devops", "mobile"] | None,
        Field(description="Topic; omit for the overview of running, upcoming and recent contests."),
    ] = None,
    contest_type: Annotated[
        Literal["featured", "other", "private"] | None,
        Field(description="featured = Quera's main contests, other = public ones. Only with category."),
    ] = None,
    organizer: Annotated[
        str | None, Field(description="Organizer slug, e.g. 'quera', 'digikala', 'snapp', 'divar'. Only with category.")
    ] = None,
    page: Page = 1,
) -> dict:
    """List Quera programming contests: with no filter, those running or upcoming now plus the latest finished ones.

    With a category it pages through the archive of that topic (10 per page, newest first). Times are UTC ISO.
    Rankings and user profiles are not offered.
    """
    if not category:
        p = await http.fetch("contest")
        return {
            "running_or_upcoming": [
                _contest(n) for k in ("activeFeaturedContests", "activeOtherContests") for n in p[k]
            ],
            "recently_finished": [_contest(n) for n in p["finishedContests"]],
            "topics": {c["name"]: c["count"] for c in p["categories"]},
        }
    q = {"category": category, "contest_type": contest_type, "organizer": organizer, "page": page if page > 1 else None}
    a = (await http.fetch(f"contest/search/{category}", q))["allContests"]
    pi = a["page_info"]
    return {
        "total": pi["total_count"],
        "page": pi["current_page"],
        "has_more": pi["has_next_page"],
        "results": [_contest(n) for n in a["nodes"]],
    }


@tool("Search Quera problems")
async def qr_problems(
    search: Annotated[str | None, Field(description="Words in the problem name.")] = None,
    tag: Annotated[
        str | None,
        Field(description="Topic slug, e.g. 'data-structures', 'python', 'django', 'back-end', 'machine-learning'."),
    ] = None,
    difficulty: Annotated[Literal["easy", "medium", "hard"] | None, Field(description="Difficulty.")] = None,
    category: Annotated[
        Literal["technology", "contest", "university", "olympiad"] | None,
        Field(description="Where the problem comes from."),
    ] = None,
    contest: Annotated[
        str | None, Field(description="Only problems of this contest: id from qr_problem_filters, e.g. '28542'.")
    ] = None,
    order: Annotated[
        Literal["new", "old", "most-solutions", "least-solutions", "most-liked", "relevant", "random"] | None,
        Field(description="Sort order; default new."),
    ] = None,
    page: Page = 1,
) -> dict:
    """Search Quera's public problemset (about 2,000 programming problems), 25 per page.

    Use to find practice problems by topic, difficulty or name. Each result has an id: call qr_problem for the statement.
    qr_problem_filters lists the topic slugs and contest ids.
    """
    q = {
        "search": search,
        "tag": tag,
        "difficulty": DIFFICULTY[difficulty] if difficulty else None,
        "category": category,
        "contest": contest,
        "order": order,
        "page": page if page > 1 else None,
    }
    p = (await http.fetch("problemset", q))["problems"]
    return _paged(p, [_problem(e["node"]) for e in p["edges"]], page, 25)


@tool("Get a Quera problem")
async def qr_problem(id: Annotated[str, Field(description="Problem id from qr_problems, e.g. '589'.")]) -> dict:
    """Get one Quera problem: statement (Markdown with LaTeX), limits, difficulty, tags, solve stats and languages.

    Call after qr_problems. Submitting solutions is not possible here.
    """
    p = (await http.fetch(f"problemset/{id}", {"pk": id}))["problem"]
    return {
        **_problem(p),
        "score": p.get("score"),
        "statement": _text(p.get("description"), 6000),
        "languages": [f["label"] for f in p.get("allowed_file_types") or []],
    }


@tool("Quera courses")
async def qr_courses(
    search: Annotated[str | None, Field(description="Words in the course name, e.g. 'پایتون', 'react'.")] = None,
    track: Annotated[
        str | None,
        Field(
            description="Learning path slug: python-django, front-end, artificial-intelligence, machinelearning, devops, data-analysis, deep-learning, php-laravel, olympiad, general."
        ),
    ] = None,
    level: Annotated[
        Literal["beginner", "advanced", "expert"] | None,
        Field(description="Course level: beginner (مقدماتی), advanced (پیشرفته), expert (تخصصی, job-ready)."),
    ] = None,
    order: Annotated[Literal["best-seller", "newest"] | None, Field(description="Sort order.")] = None,
) -> dict:
    """List Quera College's paid programming courses (about 70) with level and price.

    Use for 'which Quera course teaches X'. price_toman is the list price in Toman; your_price_toman is what a visitor
    pays now (0 = currently free). Upcoming courses (announced, not yet open) are listed separately. For intensive
    bootcamps call qr_bootcamps.
    """
    lv = {"beginner": "1", "advanced": "2", "expert": "3"}
    p = await http.fetch(
        "college", {"search": search, "track": track, "level": lv[level] if level else None, "order": order}
    )
    t = p["trackColleges"]
    return {
        "total": t["totalCount"],
        "results": [_course(e["node"]) for e in t["edges"]],
        "upcoming": [
            {"name": e["node"]["name"], "registration_starts": e["node"]["registration_start_time"]}
            for e in (p.get("futureColleges") or {}).get("edges", [])
        ],
    }


@tool("Quera job salaries")
async def qr_salaries(
    technologies: Annotated[
        list[str] | None, Field(description="Tech codes, e.g. 'python'; several mean any of them.")
    ] = None,
    city: Annotated[str | None, Field(description="City name or id, as for qr_jobs.")] = None,
    level: Annotated[
        list[Literal["intern", "junior", "mid", "senior", "lead"]] | None, Field(description="Seniority filter.")
    ] = None,
) -> dict:
    """Summarize the salaries employers published in open Quera jobs, grouped by seniority level (Toman per month).

    Use for 'how much does a junior Python developer earn'. Only postings that show a salary count (a minority: see
    jobs_with_salary against jobs_total), so treat it as a rough sample, not a market survey. Call qr_jobs with
    order='high_salary' for the postings behind it.
    """
    q = {
        "technologies": _techs(technologies),
        "city": await _city_id(city) if city else None,
        "level": [LEVELS[x] for x in level or []],
    }
    nodes: list[dict] = []
    for n in range(1, 7):  # shortcut: 90 jobs max, more than the board holds
        j = (await http.fetch("magnet/jobs", {**q, "page": n if n > 1 else None}))["jobs"]
        nodes += [e["node"] for e in j["edges"]]
        if n * 15 >= j["totalCount"]:
            break
    by_level: dict[str, list[tuple[int, int]]] = {}
    for n in nodes:
        nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", _digits(n.get("salary")) or "")]
        if nums:
            by_level.setdefault(n.get("level") or "?", []).append((nums[0], nums[-1]))
    levels = {
        lv: {
            "jobs": len(r),
            "lowest_toman": min(a for a, _ in r),
            "median_toman": int(statistics.median((a + b) / 2 for a, b in r)),
            "highest_toman": max(b for _, b in r),
        }
        for lv, r in by_level.items()
    }
    return {
        "jobs_total": len(nodes),
        "jobs_with_salary": sum(x["jobs"] for x in levels.values()),
        "by_level": levels,
        "note": "Toman per month; median is of each posting's range midpoint. Postings without a salary are not counted.",
    }


@tool("Quera problem filters")
async def qr_problem_filters() -> dict:
    """List the topic slugs, contest ids, origins and judging types that qr_problems accepts.

    Call once when unsure which tag or contest value to use in qr_problems.
    """
    out: dict[str, Any] = {}
    for f in (await http.fetch("problemset"))["problems"]["filterChoices"]["initial"]:
        if f["fieldName"] in ("tag", "contest", "type", "category"):
            out[f["fieldName"]] = {x["value"]: x["label"] for x in f["choices"]}
    return out


def _step(s: dict) -> dict:
    return {"title": s["title"], "start": s.get("start_time"), "finish": s.get("finish_time")}


@tool("Get a Quera event")
async def qr_event(
    slug: Annotated[
        str,
        Field(description="Event slug from a qr_contests url (quera.org/events/<slug>), e.g. 'codecup8-algorithm'."),
    ],
) -> dict:
    """Get a Quera event or competition page (CodeCup, hackathon, contest series): schedule, prizes, price, sub-events.

    Call after qr_contests. Participant lists and rankings are not offered.
    """
    e = (await http.fetch(f"events/{slug}", {"slug": slug}))["event"]
    return {
        "slug": slug,
        "title": e["title"],
        "kind": e.get("prefix"),
        "state": e.get("state"),
        "participants": e.get("user_count"),
        "team_event": e.get("is_team_event"),
        "team_size": [e.get("min_team_size"), e.get("max_team_size")] if e.get("is_team_event") else None,
        "price_toman": e.get("payable_price"),
        "registration_opens": e.get("registration_start_time"),
        "registration_deadline": e.get("registration_deadline"),
        "registration_closed": e.get("registration_is_closed"),
        "technologies": [t["name"] for t in e.get("technologies") or []],
        "organizers": [o.get("name") or o.get("name_fa") for o in e.get("organizers") or []],
        "sponsors": [o.get("name") for o in e.get("sponsors") or []],
        "intro": _text(e.get("intro"), 1500),
        "prizes_text": _text(e.get("awards_description"), 600),
        "prizes": [{a["achievement"]: a["award"]} for a in e.get("awards") or []],
        "steps": [_step(x) for x in e.get("steps") or []],
        "sub_events": [
            {
                "slug": c["slug"],
                "title": c["title"],
                "participants": c.get("user_count"),
                "registration_deadline": c.get("registration_deadline"),
                "registration_closed": c.get("registration_is_closed"),
                "steps": [_step(x) for x in c.get("steps") or []],
            }
            for c in e.get("children") or []
        ],
        "faq": [{"q": f["question"], "a": _text(f["answer"], 400)} for f in (e.get("faq_items") or [])[:6]],
        "url": f"{SITE}/events/{slug}",
    }


def _toman(v: Any) -> int | None:
    return int(v) if isinstance(v, int | float) else None


@tool("Quera bootcamps")
async def qr_bootcamps(
    slug: Annotated[
        str | None, Field(description="Bootcamp slug from the list (e.g. 'devops'); omit to list bootcamps.")
    ] = None,
    include_closed: Annotated[
        bool, Field(description="Also list past or closed-registration cohorts (list only).")
    ] = False,
) -> dict:
    """List Quera's intensive paid bootcamps open for registration with price, dates and seats, or get one in full.

    Without slug: cohorts you can register for now (include_closed adds past ones). With slug: syllabus by week,
    prerequisites, instructors, installments and FAQ. Prices are Toman.
    """
    if slug:
        b = (await http.fetch(f"bootcamp/{slug}", {"slug": slug}))["bootcamp"]
        return {
            "slug": slug,
            "title": b["fa_title"],
            "english_title": b["title"],
            "format": b.get("bootcamp_type_text"),
            "season": " ".join((_digits(b.get("season")) or "").split()),
            "duration": f"{_digits(b.get('week_duration'))}, {_digits(b.get('hour_duration'))}",
            "starts": b.get("start_date_time"),
            "registration_deadline": b.get("due_date"),
            "registration_open": b.get("users_can_register"),
            "seats_left": b.get("available_capacity"),
            "list_price_toman": _toman(b.get("bootcamp_base_price")),
            "price_toman": _toman(b.get("bootcamp_payable_price")),
            "pre_register_price_range_toman": [
                _toman(b.get("pre_register_min_price")),
                _toman(b.get("pre_register_max_price")),
            ],
            "installments": _text(b.get("installment_text"), 600),
            "description": _text(b.get("long_description"), 1500),
            "prerequisites": [r["name"] for r in b.get("requirements") or []],
            "syllabus": [
                {
                    "week": t.get("week_title"),
                    "topic": t.get("main_topic"),
                    "items": [x["title"] for x in t.get("titles") or []],
                }
                for t in b.get("topic_items") or []
            ],
            "instructors": [{"name": t["name"], "job": t.get("job")} for t in b.get("teachers") or []],
            "faq": [{"q": f["question"], "a": _text(f["answer"], 400)} for f in (b.get("faq_items") or [])[:8]],
            "url": f"{SITE}/bootcamp/{slug}",
        }
    plp = (await http.fetch("bootcamp"))["plp"]
    offers: dict[str, tuple[int, str | None]] = {}
    try:
        for i in json.loads(plp.get("schema") or "{}").get("itemListElement", []):
            it = i["item"]
            offers[it["url"].rsplit("/", 1)[-1]] = (
                it["offers"]["price"] // 10,
                it["hasCourseInstance"].get("startDate"),
            )
    except (ValueError, KeyError, TypeError):
        pass  # the structured data is optional: prices then show as missing
    rows = [
        {
            "slug": b["slug"],
            "title": b["fa_title"],
            "english_title": b["title"],
            "season": " ".join((_digits(b.get("season")) or "").split()),
            "duration": f"{_digits(b.get('week_duration'))}, {_digits(b.get('hour_duration'))}",
            "registration_open": b["users_can_register"],
            "registration_deadline": b["due_date"],
            "seats_left": b["available_capacity"],
            "price_toman": offers.get(b["slug"], (None, None))[0],
            "starts": offers.get(b["slug"], (None, None))[1],
            "summary": b.get("description"),
            "url": f"{SITE}/bootcamp/{b['slug']}",
        }
        for b in plp["bootcamps"]
        if include_closed or b["users_can_register"]
    ]
    return {"total": len(rows), "results": rows}


def _post(p: dict, cats: dict) -> dict:
    return {
        "slug": p["slug"],
        "title": html.unescape(p["title"]["rendered"]),
        "date": p["date"][:10],
        "categories": [cats[c]["name"] for c in p.get("categories") or [] if c in cats],
        "excerpt": _text(p["excerpt"]["rendered"], 300),
        "url": p["link"],
    }


@tool("Quera blog")
async def qr_blog(
    slug: Annotated[str | None, Field(description="Post slug from the list; omit to list posts.")] = None,
    search: Annotated[str | None, Field(description="Words to look for in posts (list only).")] = None,
    category: Annotated[
        str | None, Field(description="Category slug, e.g. 'python', 'developer', 'technology', 'basics' (list only).")
    ] = None,
    page: Page = 1,
) -> dict:
    """Search or read the Quera blog (quera.org/blog): Persian programming articles, career and tech news.

    Without slug: newest posts first, 10 per page, with excerpt and categories. With slug: the article text
    (capped at 6,000 characters; open the url for the rest).
    """
    cats = {c["id"]: c for c in await http.fetch_wp("categories", {"per_page": 100, "_fields": "id,name,slug"})}
    fields = "id,slug,date,link,title,excerpt,categories"
    if slug:
        r = await http.fetch_wp("posts", {"slug": slug, "_fields": fields + ",content"})
        if not r:
            raise ApiError("No blog post with that slug. Use qr_blog to search.")
        return {**_post(r[0], cats), "text": _text(r[0]["content"]["rendered"], 6000)}
    q: dict[str, Any] = {"per_page": 10, "page": page, "search": search, "_fields": fields}
    if category:
        match = [c["id"] for c in cats.values() if c["slug"] == category]
        if not match:
            raise ApiError("Unknown category. Valid: " + ", ".join(sorted(c["slug"] for c in cats.values())) + ".")
        q["categories"] = match[0]
    try:
        posts = await http.fetch_wp("posts", q)
    except ApiError as e:
        if e.status != 400:  # WordPress answers 400 for a page past the end
            raise
        posts = []
    return {"page": page, "has_more": len(posts) == 10, "results": [_post(x, cats) for x in posts]}
