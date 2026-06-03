"""
Standalone UFCStats fight scraper.

It scrapes:
1. all completed UFCStats event links
2. all fight links for each event
3. fight-level statistics for every fight

Default mode is hybrid:
- use Playwright once to pass the UFCStats JavaScript/browser check
- copy cookies/user-agent into requests
- scrape fight pages with requests

Install:
    pip install requests beautifulsoup4 playwright
    python -m playwright install chromium

Run:
    python ufcstats_scrape_all_fights.py --out ufc_fights.csv 

If hybrid mode still gets browser-check pages, use slower browser-only mode:
    python ufcstats_scrape_all_fights.py --out ufc_fights.csv --browser-only
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ALL_EVENTS_URL = "http://ufcstats.com/statistics/events/completed?page=all"

BASE_COLUMNS = [
    "event_name",
    "event_url",
    "fight_url",
    "date",
    "location",
    "attendance",
    "fight_type",
    "winner",
    "R_fighter",
    "B_fighter",
    "R_status",
    "B_status",
    "win_by",
    "last_round",
    "last_round_time",
    "format",
    "referee",
    "details",
]

SIDE_COLUMNS = [
    "KD",
    "SIG_STR_landed",
    "SIG_STR_att",
    "SIG_STR_pct",
    "TOTAL_STR_landed",
    "TOTAL_STR_att",
    "TD_landed",
    "TD_att",
    "TD_pct",
    "SUB_ATT",
    "REV",
    "CTRL",
    "HEAD_landed",
    "HEAD_att",
    "BODY_landed",
    "BODY_att",
    "LEG_landed",
    "LEG_att",
    "DISTANCE_landed",
    "DISTANCE_att",
    "CLINCH_landed",
    "CLINCH_att",
    "GROUND_landed",
    "GROUND_att",
]

FIELDNAMES = BASE_COLUMNS + [f"{side}_{col}" for side in ("R", "B") for col in SIDE_COLUMNS]


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def is_browser_check_page(html: str) -> bool:
    return (
        "Checking your browser" in html
        or "<title>Loading?</title>" in html
        or "This site requires JavaScript" in html
    )


def parse_int(value: str) -> Optional[int]:
    value = clean_text(value)
    if not value or value in {"--", "---"}:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_pct(value: str) -> Optional[float]:
    value = clean_text(value)
    if not value or value in {"--", "---"}:
        return None
    if value.endswith("%"):
        try:
            return float(value[:-1]) / 100.0
        except ValueError:
            return None
    return None


def parse_of(value: str) -> Tuple[Optional[int], Optional[int]]:
    value = clean_text(value)
    match = re.search(r"(\d+)\s+of\s+(\d+)", value)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def td_pair_values(td) -> Tuple[str, str]:
    values = [clean_text(p.get_text(" ", strip=True)) for p in td.find_all("p")]
    values = [v for v in values if v]

    if len(values) >= 2:
        return values[0], values[1]

    raw = clean_text(td.get_text("\n", strip=True))
    parts = [clean_text(p) for p in raw.split("\n") if clean_text(p)]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ""
    return "", ""


class UFCStatsClient:
    def __init__(self, headless: bool = True, browser_only: bool = False, delay: float = 0.0):
        self.headless = headless
        self.browser_only = browser_only
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
        )
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._bootstrapped = False

    def close(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._pw is not None:
            self._pw.stop()

    def _start_browser(self) -> None:
        if self._pw is None:
            self._pw = sync_playwright().start()
        if self._browser is None:
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self._context = self._browser.new_context()
            self._page = self._context.new_page()

    def _browser_html(self, url: str) -> str:
        self._start_browser()
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self._page.wait_for_timeout(3000)

        html = self._page.content()
        for _ in range(8):
            if not is_browser_check_page(html):
                break
            print("Browser-check page detected; waiting...", file=sys.stderr)
            self._page.wait_for_timeout(5000)
            html = self._page.content()

        if is_browser_check_page(html):
            raise RuntimeError(f"Still receiving browser-check page for {url}")

        return html

    def _bootstrap_requests_from_browser(self, url: str) -> None:
        print("Opening Playwright once to get UFCStats cookies...", file=sys.stderr)
        html = self._browser_html(url)
        assert self._page is not None
        assert self._context is not None

        user_agent = self._page.evaluate("() => navigator.userAgent")
        cookies = self._context.cookies()

        self.session.headers.update({"User-Agent": user_agent})
        for cookie in cookies:
            self.session.cookies.set(
                cookie["name"],
                cookie["value"],
                domain=cookie.get("domain"),
                path=cookie.get("path", "/"),
            )

        self._bootstrapped = True
        print(f"Copied {len(cookies)} cookies into requests session.", file=sys.stderr)

        if is_browser_check_page(html):
            raise RuntimeError("Browser did not get past the browser-check page.")

    def html(self, url: str) -> str:
        if self.browser_only:
            if self.delay:
                time.sleep(self.delay)
            return self._browser_html(url)

        if not self._bootstrapped:
            response = self.session.get(url, timeout=60)
            if is_browser_check_page(response.text):
                self._bootstrap_requests_from_browser(url)
            elif response.ok:
                self._bootstrapped = True
                return response.text

        if self.delay:
            time.sleep(self.delay)

        response = self.session.get(url, timeout=60)
        response.raise_for_status()

        if is_browser_check_page(response.text):
            raise RuntimeError(
                "requests still received the UFCStats browser-check page after Playwright cookies. "
                "Rerun with --browser-only."
            )

        return response.text

    def soup(self, url: str) -> BeautifulSoup:
        return BeautifulSoup(self.html(url), "html.parser")


def extract_event_links(soup: BeautifulSoup) -> List[str]:
    links: List[str] = []
    for a in soup.select("td.b-statistics__table-col a[href*='/event-details/']"):
        href = a.get("href")
        if href and href not in links:
            links.append(href)
    return links


def extract_fight_links(event_soup: BeautifulSoup) -> List[str]:
    links: List[str] = []
    for row in event_soup.select("tr.js-fight-details-click[data-link]"):
        href = row.get("data-link")
        if href and href not in links:
            links.append(href)
    return links


def parse_event_info(event_soup: BeautifulSoup, event_url: str) -> Dict[str, str]:
    info = {
        "event_url": event_url,
        "event_name": "",
        "date": "",
        "location": "",
        "attendance": "",
    }

    title = event_soup.select_one("h2.b-content__title")
    if title:
        info["event_name"] = clean_text(title.get_text(" ", strip=True))

    for li in event_soup.select("li.b-list__box-list-item"):
        text = clean_text(li.get_text(" ", strip=True))
        if ":" not in text:
            continue
        key, value = text.split(":", 1)
        key = clean_text(key).lower()
        value = clean_text(value)
        if key == "date":
            info["date"] = value
        elif key == "location":
            info["location"] = value
        elif key == "attendance":
            info["attendance"] = value

    return info


def parse_people(fight_soup: BeautifulSoup) -> Dict[str, str]:
    out = {
        "R_fighter": "",
        "B_fighter": "",
        "R_status": "",
        "B_status": "",
        "winner": "",
    }

    people = fight_soup.select("div.b-fight-details__person")
    for idx, person in enumerate(people[:2]):
        side = "R" if idx == 0 else "B"
        name_el = person.select_one("h3.b-fight-details__person-name")
        status_el = person.select_one("i.b-fight-details__person-status")
        name = clean_text(name_el.get_text(" ", strip=True)) if name_el else ""
        status = clean_text(status_el.get_text(" ", strip=True)) if status_el else ""

        out[f"{side}_fighter"] = name
        out[f"{side}_status"] = status
        if status.upper() == "W":
            out["winner"] = name

    return out


def parse_fight_meta(fight_soup: BeautifulSoup) -> Dict[str, str]:
    out = {
        "fight_type": "",
        "win_by": "",
        "last_round": "",
        "last_round_time": "",
        "format": "",
        "referee": "",
        "details": "",
    }

    title = fight_soup.select_one("i.b-fight-details__fight-title")
    if title:
        out["fight_type"] = clean_text(title.get_text(" ", strip=True))

    item_selector = (
        "p.b-fight-details__text i.b-fight-details__text-item, "
        "p.b-fight-details__text i.b-fight-details__text-item_first"
    )
    for item in fight_soup.select(item_selector):
        label = item.select_one("i.b-fight-details__label")
        if label is None:
            continue
        label_text = clean_text(label.get_text(" ", strip=True)).rstrip(":")
        value = clean_text(item.get_text(" ", strip=True)).replace(clean_text(label.get_text(" ", strip=True)), "", 1).strip()

        if label_text == "Method":
            out["win_by"] = value
        elif label_text == "Round":
            out["last_round"] = value
        elif label_text == "Time":
            out["last_round_time"] = value
        elif label_text == "Time format":
            out["format"] = value
        elif label_text == "Referee":
            out["referee"] = value
        elif label_text == "Details":
            out["details"] = value

    return out


def add_of_stat(row: Dict[str, object], side: str, stat: str, raw: str) -> None:
    landed, attempted = parse_of(raw)
    row[f"{side}_{stat}_landed"] = landed
    row[f"{side}_{stat}_att"] = attempted


def parse_stats_tables(fight_soup: BeautifulSoup) -> Dict[str, object]:
    row: Dict[str, object] = {}
    tables = fight_soup.find_all("tbody")
    if len(tables) < 3:
        raise ValueError("Could not find expected UFCStats stats tables.")

    total_cols = [
        "fighter",
        "KD",
        "SIG_STR",
        "SIG_STR_pct",
        "TOTAL_STR",
        "TD",
        "TD_pct",
        "SUB_ATT",
        "REV",
        "CTRL",
    ]
    sig_cols = [
        "fighter",
        "SIG_STR",
        "SIG_STR_pct",
        "HEAD",
        "BODY",
        "LEG",
        "DISTANCE",
        "CLINCH",
        "GROUND",
    ]

    total_tds = tables[0].find("tr").find_all("td", recursive=False)
    for idx, col in enumerate(total_cols):
        if idx >= len(total_tds):
            continue
        r_value, b_value = td_pair_values(total_tds[idx])

        if col == "fighter":
            row["R_fighter"] = r_value
            row["B_fighter"] = b_value
        elif col in {"SIG_STR", "TOTAL_STR", "TD"}:
            add_of_stat(row, "R", col, r_value)
            add_of_stat(row, "B", col, b_value)
        elif col in {"SIG_STR_pct", "TD_pct"}:
            row[f"R_{col}"] = parse_pct(r_value)
            row[f"B_{col}"] = parse_pct(b_value)
        elif col in {"KD", "SUB_ATT", "REV"}:
            row[f"R_{col}"] = parse_int(r_value)
            row[f"B_{col}"] = parse_int(b_value)
        else:
            row[f"R_{col}"] = r_value
            row[f"B_{col}"] = b_value

    sig_tds = tables[2].find("tr").find_all("td", recursive=False)
    for idx, col in enumerate(sig_cols):
        if idx >= len(sig_tds):
            continue
        r_value, b_value = td_pair_values(sig_tds[idx])
        if col in {"HEAD", "BODY", "LEG", "DISTANCE", "CLINCH", "GROUND"}:
            add_of_stat(row, "R", col, r_value)
            add_of_stat(row, "B", col, b_value)

    return row


def parse_fight_page(fight_soup: BeautifulSoup, fight_url: str, event_info: Dict[str, str]) -> Dict[str, object]:
    row: Dict[str, object] = {name: "" for name in FIELDNAMES}
    row.update(event_info)
    row["fight_url"] = fight_url

    row.update(parse_people(fight_soup))
    row.update(parse_fight_meta(fight_soup))
    row.update(parse_stats_tables(fight_soup))

    return row


def scrape_one_fight(client: UFCStatsClient, fight_url: str, event_info: Dict[str, str]) -> Dict[str, object]:
    fight_soup = client.soup(fight_url)
    return parse_fight_page(fight_soup, fight_url, event_info)


def scrape_all_fights(
    out_path: Path,
    headless: bool,
    browser_only: bool,
    workers: int,
    delay: float,
    limit_events: Optional[int],
    limit_fights: Optional[int],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    failed_path = out_path.with_suffix(".failed.csv")

    client = UFCStatsClient(headless=headless, browser_only=browser_only, delay=delay)
    if browser_only:
        workers = 1

    total_written = 0
    failures: List[Dict[str, str]] = []

    try:
        print("Getting completed event links...")
        events_soup = client.soup(ALL_EVENTS_URL)
        event_links = extract_event_links(events_soup)
        if limit_events is not None:
            event_links = event_links[:limit_events]

        if not event_links:
            raise RuntimeError("No event links found. UFCStats page may not have loaded correctly.")

        print(f"Found {len(event_links)} events.")

        with out_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            writer.writeheader()

            for event_index, event_url in enumerate(event_links, start=1):
                print(f"[{event_index}/{len(event_links)}] Event: {event_url}")
                event_soup = client.soup(event_url)
                event_info = parse_event_info(event_soup, event_url)
                fight_links = extract_fight_links(event_soup)
                if limit_fights is not None:
                    fight_links = fight_links[:limit_fights]

                print(f"  Found {len(fight_links)} fights.")
                if not fight_links:
                    failures.append({"event_url": event_url, "fight_url": "", "error": "No fight links found"})
                    continue

                if workers <= 1:
                    for fight_url in fight_links:
                        try:
                            row = scrape_one_fight(client, fight_url, event_info)
                            writer.writerow(row)
                            total_written += 1
                        except Exception as exc:
                            print(f"  FAILED fight {fight_url}: {exc}", file=sys.stderr)
                            failures.append({"event_url": event_url, "fight_url": fight_url, "error": str(exc)})
                else:
                    with ThreadPoolExecutor(max_workers=workers) as executor:
                        future_to_url = {
                            executor.submit(scrape_one_fight, client, fight_url, event_info): fight_url
                            for fight_url in fight_links
                        }
                        for future in as_completed(future_to_url):
                            fight_url = future_to_url[future]
                            try:
                                row = future.result()
                                writer.writerow(row)
                                total_written += 1
                            except Exception as exc:
                                print(f"  FAILED fight {fight_url}: {exc}", file=sys.stderr)
                                failures.append({"event_url": event_url, "fight_url": fight_url, "error": str(exc)})

                f.flush()
                print(f"  Total fights written: {total_written}")

    finally:
        client.close()

    if failures:
        with failed_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["event_url", "fight_url", "error"])
            writer.writeheader()
            writer.writerows(failures)
        print(f"Finished with {len(failures)} failures. See: {failed_path}", file=sys.stderr)

    print(f"Done. Wrote {total_written} fights to {out_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape all UFCStats fight statistics into CSV.")
    parser.add_argument("--out", type=Path, default=Path("data/ufc_fights.csv"), help="Output CSV path.")
    parser.add_argument("--headless", action="store_true", help="Run Chromium without showing the browser window.")
    parser.add_argument("--browser-only", action="store_true", help="Use Playwright for every page. Slower, but useful if cookies do not work with requests.")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel fight-page requests in hybrid mode.")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay in seconds before each request/page load.")
    parser.add_argument("--limit-events", type=int, default=None, help="Debug option: only scrape first N events.")
    parser.add_argument("--limit-fights", type=int, default=None, help="Debug option: only scrape first N fights per event.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    scrape_all_fights(
        out_path=args.out,
        headless=args.headless,
        browser_only=args.browser_only,
        workers=args.workers,
        delay=args.delay,
        limit_events=args.limit_events,
        limit_fights=args.limit_fights,
    )
