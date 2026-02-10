#!/usr/bin/env python3
"""Scrape company names and domains from cpgd.xyz/brandbuilders (all pages)."""

import csv
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

BASE_URL = "https://www.cpgd.xyz"

# Pagination param discovered from the site
PAGE_PARAM = "9d708921_page"


def get_builders_from_all_pages():
    """Get all builder names and slugs from all paginated directory pages."""
    builders = []
    seen_slugs = set()
    page = 1

    while True:
        if page == 1:
            url = f"{BASE_URL}/brandbuilders"
        else:
            url = f"{BASE_URL}/brandbuilders?{PAGE_PARAM}={page}"

        print(f"  Fetching page {page}: {url}")
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        page_builders = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/builder/"):
                slug = href.replace("/builder/", "")
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    name = a.get_text(strip=True)
                    if not name:
                        for child in a.descendants:
                            if isinstance(child, str) and child.strip():
                                name = child.strip()
                                break
                    page_builders.append({"slug": slug, "name": name})

        if not page_builders:
            print(f"  Page {page} has no new builders, stopping.")
            break

        builders.extend(page_builders)
        print(f"  Found {len(page_builders)} builders on page {page} (total: {len(builders)})")
        page += 1

    return builders


def slug_to_name(slug):
    """Convert a URL slug to a human-readable company name."""
    cleaned = re.sub(r'-[a-f0-9]{5}$', '', slug)
    name = cleaned.replace("-", " ").title()
    name = name.replace(" Llc", " LLC")
    name = name.replace(" Inc", " Inc.")
    name = name.replace(" Ltd", " Ltd.")
    name = name.replace(" Co ", " Co. ")
    if name.endswith(" Co"):
        name = name + "."
    name = name.replace(" Ai", " AI")
    name = name.replace(" Pr", " PR")
    name = name.replace(" Fx", " FX")
    return name


def scrape_builder_domain(slug):
    """Scrape a single builder profile page for domain."""
    url = f"{BASE_URL}/builder/{slug}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return {"slug": slug, "domain": "", "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    skip_patterns = [
        "cpgd.xyz", "twitter.com", "instagram.com", "tiktok.com",
        "linkedin.com", "facebook.com", "youtube.com", "webflow.com",
        "x.com",
    ]

    # Strategy 1: Look for external links that aren't social/cpgd
    external_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "cpgd.xyz" not in href:
            if any(s in href.lower() for s in skip_patterns):
                continue
            external_links.append(href)

    # Strategy 2: Look for text that looks like a domain
    tld_pattern = (
        r'(?:com|co|io|xyz|net|org|agency|studio|design|dev|ai|inc|us|uk|ca|nyc|'
        r'land|space|biz|consulting|cc|gg|marketing|media|digital|group|works|'
        r'so|ly|me|tv|app|pro|tech|ventures|world)'
    )
    domain_pattern = re.compile(
        r'\b([a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?\.' + tld_pattern + r'(?:\.[a-z]{2})?)\b'
    )

    skip_domains = {
        "cpgd.xyz", "www.cpgd.xyz", "twitter.com", "www.twitter.com",
        "instagram.com", "www.instagram.com", "tiktok.com", "www.tiktok.com",
        "webflow.com", "linkedin.com", "www.linkedin.com",
        "facebook.com", "www.facebook.com", "youtube.com", "www.youtube.com",
        "x.com", "www.x.com",
    }

    page_text = soup.get_text()
    found_domains = domain_pattern.findall(page_text)

    candidate_domains = []
    for match in found_domains:
        d = match[0].lower()
        if d not in skip_domains and not d.endswith("cpgd.xyz"):
            candidate_domains.append(d)

    # Strategy 3: Look for mailto links
    email_domain = ""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0]
            if "@" in email:
                email_domain = email.split("@")[1]

    # Pick best domain
    domain = ""
    if candidate_domains:
        domain = candidate_domains[0]
    elif external_links:
        parsed = urlparse(external_links[0])
        domain = parsed.netloc.replace("www.", "")
    elif email_domain:
        domain = email_domain

    # Clean up: remove any "http" or "https" only results
    if domain in ("http", "https", ""):
        # Try harder with external links
        if external_links:
            parsed = urlparse(external_links[0])
            d = parsed.netloc.replace("www.", "")
            if d and d not in ("http", "https"):
                domain = d
        elif email_domain:
            domain = email_domain
        else:
            domain = ""

    return {"slug": slug, "domain": domain, "error": ""}


def main():
    print("Fetching all builder listings (paginated)...")
    builders = get_builders_from_all_pages()
    print(f"\nTotal builders found across all pages: {len(builders)}")

    # Scrape domains from individual pages
    results = []
    slug_to_builder = {b["slug"]: b for b in builders}

    print(f"\nScraping {len(builders)} individual profile pages...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_slug = {
            executor.submit(scrape_builder_domain, b["slug"]): b["slug"]
            for b in builders
        }

        for i, future in enumerate(as_completed(future_to_slug)):
            result = future.result()
            slug = result["slug"]
            builder = slug_to_builder[slug]

            name = builder.get("name", "") or slug_to_name(slug)

            results.append({
                "name": name,
                "domain": result["domain"],
                "slug": slug,
                "error": result.get("error", ""),
            })

            if (i + 1) % 25 == 0:
                print(f"  Scraped {i + 1}/{len(builders)}...")

    # Sort by original order
    slug_order = {b["slug"]: i for i, b in enumerate(builders)}
    results.sort(key=lambda r: slug_order.get(r["slug"], 999))

    # Write CSV
    output_file = "company_data.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "domain", "slug", "error"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults written to {output_file}")
    print(f"Total companies: {len(results)}")

    with_domain = sum(1 for r in results if r["domain"])
    print(f"Companies with domain found: {with_domain}")
    print(f"Companies without domain: {len(results) - with_domain}")

    # Print table
    print(f"\n{'#':<5} {'Company Name':<55} {'Domain':<40}")
    print("-" * 100)
    for i, r in enumerate(results, 1):
        print(f"{i:<5} {r['name']:<55} {r['domain']:<40}")


if __name__ == "__main__":
    main()
