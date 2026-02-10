#!/usr/bin/env python3
"""Scrape company names and domains from cpgd.xyz/brandbuilders."""

import csv
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

BASE_URL = "https://www.cpgd.xyz"


def get_builders_from_listing():
    """Get all builder names and slugs from the main directory page."""
    resp = requests.get(f"{BASE_URL}/brandbuilders", timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    builders = []
    seen_slugs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/builder/"):
            slug = href.replace("/builder/", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                # Try to get the company name from the link text or parent
                name = a.get_text(strip=True)
                # Sometimes the name is in a child element
                if not name:
                    # Check for text in child elements
                    for child in a.descendants:
                        if isinstance(child, str) and child.strip():
                            name = child.strip()
                            break
                builders.append({"slug": slug, "name": name})
    return builders


def slug_to_name(slug):
    """Convert a URL slug to a human-readable company name."""
    # Remove trailing hash suffixes like '-b2f02' or '-c5ced' or '-16184' etc.
    cleaned = re.sub(r'-[a-f0-9]{5}$', '', slug)
    # Replace hyphens with spaces and title case
    name = cleaned.replace("-", " ").title()
    # Fix common patterns
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

    domain = ""

    skip_patterns = [
        "cpgd.xyz", "twitter.com", "instagram.com", "tiktok.com",
        "linkedin.com", "facebook.com", "youtube.com", "webflow.com",
        "x.com",
    ]

    # Strategy 1: Look for external links that aren't social media or cpgd
    external_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("http") and "cpgd.xyz" not in href:
            if any(s in href.lower() for s in skip_patterns):
                continue
            external_links.append(href)

    # Strategy 2: Look for text that looks like a domain
    # Extended TLD list
    tld_pattern = r'(?:com|co|io|xyz|net|org|agency|studio|design|dev|ai|inc|us|uk|ca|nyc|land|space|biz|consulting)'
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

    # Strategy 3: Look for mailto links to extract domain
    email_domain = ""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0]
            if "@" in email:
                email_domain = email.split("@")[1]

    # Priority: domain text in page > external link > email domain
    # Domain text is often the most reliable as it's displayed on the page
    if candidate_domains:
        domain = candidate_domains[0]
    elif external_links:
        parsed = urlparse(external_links[0])
        domain = parsed.netloc.replace("www.", "")
    elif email_domain:
        domain = email_domain

    return {"slug": slug, "domain": domain, "error": ""}


def main():
    print("Fetching builder listing...")
    builders = get_builders_from_listing()
    print(f"Found {len(builders)} builders")

    # Scrape domains from individual pages
    results = []
    slug_to_builder = {b["slug"]: b for b in builders}

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_slug = {
            executor.submit(scrape_builder_domain, b["slug"]): b["slug"]
            for b in builders
        }

        for i, future in enumerate(as_completed(future_to_slug)):
            result = future.result()
            slug = result["slug"]
            builder = slug_to_builder[slug]

            # Use listing name, fall back to slug-derived name
            name = builder.get("name", "") or slug_to_name(slug)

            results.append({
                "name": name,
                "domain": result["domain"],
                "slug": slug,
                "error": result.get("error", ""),
            })

            if (i + 1) % 10 == 0:
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
    print(f"\n{'Company Name':<50} {'Domain':<40}")
    print("-" * 90)
    for r in results:
        print(f"{r['name']:<50} {r['domain']:<40}")


if __name__ == "__main__":
    main()
