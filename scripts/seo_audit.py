#!/usr/bin/env python3
"""Bot Builder Landing Page SEO Audit.

Audits https://kai-agi.com/chast/bot-builder/ for SEO completeness.
Outputs JSON + human-readable summary. Exit 0 if all pass, exit 1 if failures.

Usage:
    python3 scripts/seo_audit.py [--url https://...] [--json]
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict, field
from typing import Optional


DEFAULT_URL = "https://kai-agi.com/chast/bot-builder/"


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""
    severity: str = "error"  # error | warning | info


@dataclass
class Report:
    url: str
    fetched_at: str = ""
    checks: list[Check] = field(default_factory=list)
    _html: str = ""
    _response_code: int = 0

    @property
    def passed_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "fetched_at": self.fetched_at,
            "passed": self.passed_count,
            "failed": self.failed_count,
            "checks": [asdict(c) for c in self.checks],
        }


def fetch_html(url: str, timeout: int = 15) -> tuple[str, int]:
    """Fetch page HTML and return (html, status_code)."""
    req = urllib.request.Request(url, headers={"User-Agent": "SEO-AuditBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.status
    except urllib.error.HTTPError as e:
        return "", e.code
    except Exception as e:
        return "", 0


def check_status(report: Report) -> None:
    """Verify page returns 200."""
    report.checks.append(Check(
        name="http_status",
        passed=report._response_code == 200,
        detail=f"HTTP {report._response_code}" if report._response_code else str(report._response_code),
        severity="error",
    ))


def check_title(report: Report) -> None:
    """title exists and < 60 chars."""
    m = re.search(r"<title[^>]*>([^<]+)</title>", report._html, re.IGNORECASE)
    if not m:
        report.checks.append(Check(name="title_exists", passed=False,
                                 detail="<title> tag not found", severity="error"))
        return
    title = m.group(1).strip()
    ok = len(title) <= 60
    report.checks.append(Check(
        name="title_exists",
        passed=True,
        detail=f'"{title}" ({len(title)} chars)',
    ))
    report.checks.append(Check(
        name="title_length",
        passed=ok,
        detail=f"{len(title)} chars (limit 60)" if not ok else "OK",
        severity="warning" if not ok else "info",
    ))


def check_meta_description(report: Report) -> None:
    """meta description exists, 120-160 chars."""
    m = re.search(
        r'<meta\s+(?:name="description"\s+content="([^"]+)"|content="([^"]+)"\s+name="description")',
        report._html, re.IGNORECASE,
    )
    if not m:
        report.checks.append(Check(name="meta_description", passed=False,
                                 detail="<meta name='description'> not found", severity="error"))
        return
    desc = (m.group(1) or m.group(2)).strip()
    ok = 120 <= len(desc) <= 160
    report.checks.append(Check(
        name="meta_description",
        passed=ok,
        detail=f"{len(desc)} chars — {'OK' if ok else 'should be 120-160'}",
        severity="error" if not ok else "info",
    ))


def _meta_property(html: str, prop: str) -> Optional[str]:
    """Extract og: or twitter: meta content value."""
    m = re.search(
        rf'<meta\s+(?:property="{prop}"\s+content="([^"]+)"|'
        rf'content="([^"]+)"\s+property="{prop}"|'
        rf'name="{prop}"\s+content="([^"]+)"|'
        rf'content="([^"]+)"\s+name="{prop}")',
        html, re.IGNORECASE,
    )
    for g in (m.group(1), m.group(2), m.group(3), m.group(4)):
        if g:
            return g.strip()
    return None


def check_og_tags(report: Report) -> None:
    """og:title, og:description, og:image, og:url, og:type all present."""
    required = ["og:title", "og:description", "og:image", "og:url", "og:type"]
    all_present = True
    details = []
    for prop in required:
        val = _meta_property(report._html, prop)
        if val:
            details.append(f"og:{prop.split(':')[1]}: OK")
        else:
            details.append(f"og:{prop.split(':')[1]}: MISSING")
            all_present = False
    report.checks.append(Check(
        name="og_tags",
        passed=all_present,
        detail=" | ".join(details),
        severity="error" if not all_present else "info",
    ))


def check_twitter_tags(report: Report) -> None:
    """twitter:card, twitter:title, twitter:description, twitter:image all present."""
    required = ["twitter:card", "twitter:title", "twitter:description", "twitter:image"]
    all_present = True
    details = []
    for prop in required:
        val = _meta_property(report._html, prop)
        short = prop.split(":")[1]
        if val:
            details.append(f"{short}: OK")
        else:
            details.append(f"{short}: MISSING")
            all_present = False
    report.checks.append(Check(
        name="twitter_tags",
        passed=all_present,
        detail=" | ".join(details),
        severity="error" if not all_present else "info",
    ))


def check_canonical(report: Report) -> None:
    """rel=canonical present and points to the expected URL."""
    m = re.search(r'<link\s+[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', report._html, re.IGNORECASE)
    m2 = re.search(r'<link\s+[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']canonical["\']', report._html, re.IGNORECASE)
    href = (m.group(1) if m else m2.group(1) if m2 else None) if m or m2 else None
    if not href:
        report.checks.append(Check(name="canonical", passed=False,
                                 detail="<link rel='canonical'> not found", severity="error"))
        return
    ok = href.strip().rstrip("/") == report.url.rstrip("/")
    report.checks.append(Check(
        name="canonical",
        passed=ok,
        detail=f'canonical="{href}"' + ("" if ok else f" (expected: {report.url})"),
        severity="error" if not ok else "info",
    ))


def check_jsonld(report: Report) -> None:
    """JSON-LD schema (Organization or WebSite) present."""
    m = re.search(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', report._html, re.IGNORECASE | re.DOTALL)
    if not m:
        report.checks.append(Check(name="jsonld_schema", passed=False,
                                 detail="JSON-LD <script> not found", severity="error"))
        return
    try:
        data = json.loads(m.group(1))
        types = data.get("@type", [])
        if isinstance(types, str):
            types = [types]
        valid = {"Organization", "WebSite", "WebPage"}.intersection(set(types))
        report.checks.append(Check(
            name="jsonld_schema",
            passed=bool(valid),
            detail=f"@type: {', '.join(valid) if valid else 'not Organization/WebSite'}",
            severity="error" if not valid else "info",
        ))
    except json.JSONDecodeError:
        report.checks.append(Check(name="jsonld_schema", passed=False,
                                 detail="JSON-LD present but invalid JSON", severity="error"))


def check_viewport(report: Report) -> None:
    """viewport meta tag present."""
    m = re.search(r'<meta\s+[^>]*name=["\']viewport["\'][^>]*>', report._html, re.IGNORECASE)
    report.checks.append(Check(
        name="viewport",
        passed=bool(m),
        detail="viewport meta tag found" if m else "viewport meta tag not found",
        severity="error" if not m else "info",
    ))


def check_resources(report: Report) -> None:
    """All linked resources (img, link[href], script[src]) return 200."""
    # Extract resource URLs from src= and href= attributes
    srcs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', report._html)
    # Filter to absolute URLs only (skip relative paths, #, javascript:, etc.)
    resource_urls = [
        u for u in srcs
        if u.startswith("http") and not u.startswith("data:")
    ]
    if not resource_urls:
        report.checks.append(Check(
            name="resources_all_200",
            passed=True,
            detail="No external resources found to check",
            severity="info",
        ))
        return

    failed = []
    for url in resource_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SEO-AuditBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    failed.append(f"{resp.status}: {url}")
        except Exception:
            failed.append(f"ERR: {url}")

    report.checks.append(Check(
        name="resources_all_200",
        passed=not failed,
        detail=f"{len(resource_urls)} checked, {len(failed)} failed — "
               + (", ".join(failed[:3]) + ("..." if len(failed) > 3 else "") if failed else "all OK"),
        severity="error" if failed else "info",
    ))


def run_audit(url: str) -> Report:
    from datetime import datetime, timezone
    report = Report(url=url, fetched_at=datetime.now(timezone.utc).isoformat())
    report._html, report._response_code = fetch_html(url)
    check_status(report)
    if not report._html:
        return report

    check_title(report)
    check_meta_description(report)
    check_og_tags(report)
    check_twitter_tags(report)
    check_canonical(report)
    check_jsonld(report)
    check_viewport(report)
    check_resources(report)
    return report


def print_summary(report: Report) -> None:
    print(f"\n{'='*60}")
    print(f"SEO Audit — {report.url}")
    print(f"{'='*60}")
    print(f"Fetched: {report.fetched_at}")
    print()
    for check in report.checks:
        icon = "✅" if check.passed else "❌"
        sev = f" [{check.severity}]" if check.severity != "error" else ""
        print(f"  {icon} {check.name}{sev}")
        if check.detail:
            print(f"     {check.detail}")
    print()
    print(f"Result: {report.passed_count} passed, {report.failed_count} failed")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bot Builder Landing Page SEO Audit")
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--json", action="store_true", help="Output only JSON")
    args = parser.parse_args()

    report = run_audit(args.url)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_summary(report)

    sys.exit(0 if report.failed_count == 0 else 1)
