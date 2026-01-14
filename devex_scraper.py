#!/usr/bin/env python3
"""
Devex scraper (polite, robots-aware).

This script is intended for scraping *publicly available* Devex pages.
It includes:
- robots.txt checking (can be disabled with --ignore-robots)
- basic rate limiting
- safe internal-link discovery (optional)
- JSONL output for easy downstream processing

Note: Devex may change HTML structure over time and may block aggressive scraping.
"""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, asdict
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_BASE_URL = "https://www.devex.com/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    status_code: int
    title: str | None
    description: str | None
    h1: str | None
    canonical_url: str | None
    links: list[str]
    extracted_at_epoch_s: int


class RobotsCache:
    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        robots_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
        rp = self._cache.get(robots_url)
        if rp is None:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(robots_url)
            try:
                rp.read()
            except Exception:
                # If robots is unreachable, default to allowing (common scraper behavior),
                # but still scrape politely (rate limit, limited crawl).
                self._cache[robots_url] = rp
                return True
            self._cache[robots_url] = rp
        try:
            return rp.can_fetch(self._user_agent, url)
        except Exception:
            return True


def normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    href = href.strip()
    if href.startswith("#"):
        return None
    if href.lower().startswith(("mailto:", "tel:", "javascript:")):
        return None
    joined = urllib.parse.urljoin(base, href)
    parsed = urllib.parse.urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        return None
    # Remove fragment; keep query.
    parsed = parsed._replace(fragment="")
    return urllib.parse.urlunparse(parsed)


def same_domain(a: str, b: str) -> bool:
    pa = urllib.parse.urlparse(a)
    pb = urllib.parse.urlparse(b)
    return pa.netloc.lower() == pb.netloc.lower()


def extract_page_data(url: str, status_code: int, html: str) -> ScrapedPage:
    soup = BeautifulSoup(html, "lxml")

    title = soup.title.get_text(strip=True) if soup.title else None

    description = None
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        description = desc_tag["content"].strip()

    h1 = None
    h1_tag = soup.find("h1")
    if h1_tag:
        h1 = h1_tag.get_text(" ", strip=True) or None

    canonical_url = None
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    if canon_tag and canon_tag.get("href"):
        canonical_url = normalize_url(url, canon_tag["href"])

    links: list[str] = []
    for a in soup.find_all("a", href=True):
        nu = normalize_url(url, a["href"])
        if nu:
            links.append(nu)
    # de-dupe while keeping order
    seen: set[str] = set()
    links_unique: list[str] = []
    for l in links:
        if l not in seen:
            seen.add(l)
            links_unique.append(l)

    return ScrapedPage(
        url=url,
        status_code=status_code,
        title=title,
        description=description,
        h1=h1,
        canonical_url=canonical_url,
        links=links_unique,
        extracted_at_epoch_s=int(time.time()),
    )


def build_session(user_agent: str, timeout_s: int) -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
            "Connection": "keep-alive",
        }
    )
    # Store timeout on session for convenience.
    s.request = _wrap_request_with_timeout(s.request, timeout_s)  # type: ignore[method-assign]
    return s


def _wrap_request_with_timeout(fn, timeout_s: int):
    def wrapped(method, url, **kwargs):
        if "timeout" not in kwargs:
            kwargs["timeout"] = timeout_s
        return fn(method, url, **kwargs)

    return wrapped


def polite_sleep(min_delay_s: float, max_delay_s: float) -> None:
    if max_delay_s <= 0:
        return
    d = random.uniform(min_delay_s, max_delay_s)
    time.sleep(d)


def fetch_html(session: requests.Session, url: str) -> tuple[int, str]:
    resp = session.get(url, allow_redirects=True)
    resp.raise_for_status()
    return resp.status_code, resp.text


def iter_discovered_internal_links(base_url: str, links: Iterable[str]) -> Iterable[str]:
    for l in links:
        if same_domain(base_url, l):
            yield l


def scrape(
    start_url: str,
    *,
    max_pages: int,
    discover: bool,
    user_agent: str,
    timeout_s: int,
    min_delay_s: float,
    max_delay_s: float,
    ignore_robots: bool,
    html_file: Optional[str] = None,
) -> list[ScrapedPage]:
    robots = RobotsCache(user_agent=user_agent)
    session = build_session(user_agent=user_agent, timeout_s=timeout_s)

    to_visit: list[str] = [start_url]
    visited: set[str] = set()
    results: list[ScrapedPage] = []

    while to_visit and len(results) < max_pages:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        if not ignore_robots and not robots.can_fetch(url):
            continue

        polite_sleep(min_delay_s, max_delay_s)

        try:
            if html_file and len(results) == 0:
                with open(html_file, "r", encoding="utf-8") as f:
                    html = f.read()
                status_code = 200
                page = extract_page_data(url, status_code, html)
            else:
                status_code, html = fetch_html(session, url)
                page = extract_page_data(url, status_code, html)
        except requests.HTTPError as e:
            status = getattr(getattr(e, "response", None), "status_code", 0) or 0
            results.append(
                ScrapedPage(
                    url=url,
                    status_code=status,
                    title=None,
                    description=None,
                    h1=None,
                    canonical_url=None,
                    links=[],
                    extracted_at_epoch_s=int(time.time()),
                )
            )
            continue
        except Exception:
            results.append(
                ScrapedPage(
                    url=url,
                    status_code=0,
                    title=None,
                    description=None,
                    h1=None,
                    canonical_url=None,
                    links=[],
                    extracted_at_epoch_s=int(time.time()),
                )
            )
            continue

        results.append(page)

        if discover:
            for l in iter_discovered_internal_links(start_url, page.links):
                if l not in visited and l not in to_visit:
                    to_visit.append(l)

    return results


def write_jsonl(pages: list[ScrapedPage], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for p in pages:
            f.write(json.dumps(asdict(p), ensure_ascii=False) + "\n")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape Devex pages (public HTML).")
    p.add_argument("--url", default=DEFAULT_BASE_URL, help="Start URL (default: Devex homepage).")
    p.add_argument("--max-pages", type=int, default=3, help="Max pages to fetch (default: 3).")
    p.add_argument(
        "--discover",
        action="store_true",
        help="Discover and crawl additional internal links from each page (bounded by --max-pages).",
    )
    p.add_argument("--out", default="devex_pages.jsonl", help="Output JSONL file (default: devex_pages.jsonl).")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header to send.")
    p.add_argument("--timeout", type=int, default=25, help="HTTP timeout seconds (default: 25).")
    p.add_argument("--min-delay", type=float, default=0.75, help="Min delay between requests (default: 0.75s).")
    p.add_argument("--max-delay", type=float, default=2.0, help="Max delay between requests (default: 2.0s).")
    p.add_argument("--ignore-robots", action="store_true", help="Ignore robots.txt (not recommended).")
    p.add_argument(
        "--html-file",
        default=None,
        help="Parse first page from a local HTML file instead of fetching (useful for debugging).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    pages = scrape(
        args.url,
        max_pages=args.max_pages,
        discover=args.discover,
        user_agent=args.user_agent,
        timeout_s=args.timeout,
        min_delay_s=args.min_delay,
        max_delay_s=args.max_delay,
        ignore_robots=args.ignore_robots,
        html_file=args.html_file,
    )
    write_jsonl(pages, args.out)
    print(f"Wrote {len(pages)} pages to {args.out}")


if __name__ == "__main__":
    main()

