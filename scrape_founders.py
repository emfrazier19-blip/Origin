#!/usr/bin/env python3
"""Scrape founder contact emails from cpgd.xyz builder profiles."""

import csv
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://www.cpgd.xyz"


def scrape_founder_email(slug):
    """Scrape a builder profile page for contact email."""
    url = f"{BASE_URL}/builder/{slug}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        return {"slug": slug, "email": "", "founder_name": "", "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text()

    # Find email addresses on the page
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    emails = email_pattern.findall(text)

    # Also check mailto links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0]
            if email and email not in emails:
                emails.insert(0, email)

    # Filter out cpgd/social emails, prefer company domain emails
    skip = ["cpgd.xyz", "webflow.com", "sentry.io", "example.com"]
    filtered = [e for e in emails if not any(s in e.lower() for s in skip)]

    email = filtered[0] if filtered else ""

    # Try to extract a name from the email prefix
    founder_name = ""
    if email:
        prefix = email.split("@")[0]
        # Skip generic prefixes
        generic = ["info", "hello", "hi", "contact", "team", "studio", "hey",
                    "support", "admin", "office", "work", "general", "mail",
                    "enquiries", "inquiries", "partnerships", "careers"]
        if prefix.lower() not in generic:
            # Convert email prefix to name (e.g., "trevor" -> "Trevor", "john.doe" -> "John Doe")
            name_parts = re.split(r'[._]', prefix)
            founder_name = " ".join(p.capitalize() for p in name_parts if p.isalpha())

    return {"slug": slug, "email": email, "founder_name": founder_name, "error": ""}


def main():
    # Read existing CSV
    with open("company_data.csv", "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Get slugs that need founder data
    to_scrape = [r for r in rows if not r.get("founder1_email", "").strip()]
    print(f"Companies needing founder email: {len(to_scrape)}")

    # Scrape in parallel
    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(scrape_founder_email, r["slug"]): r["slug"]
            for r in to_scrape
        }
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            results[result["slug"]] = result
            if (i + 1) % 25 == 0:
                print(f"  Scraped {i + 1}/{len(to_scrape)}...")

    # Update rows
    updated = 0
    for row in rows:
        slug = row["slug"]
        if slug in results:
            r = results[slug]
            if r["email"]:
                row["founder1_email"] = r["email"]
                if r["founder_name"]:
                    row["founder1_full_name"] = r["founder_name"]
                updated += 1

    # Write updated CSV
    fieldnames = ["name", "domain", "slug", "error", "founder1_full_name", "founder1_email", "founder2_full_name", "founder2_email"]
    with open("company_data.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nUpdated {updated} companies with founder emails")
    print(f"Total companies: {len(rows)}")

    # Summary
    with_email = sum(1 for r in rows if r.get("founder1_email", "").strip())
    print(f"Companies with founder email: {with_email}")
    print(f"Companies without: {len(rows) - with_email}")


if __name__ == "__main__":
    main()
