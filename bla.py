import os
import re
import json
import yaml
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_CADC_URL = "https://www.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/en/meetings/"

def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)

def get_cadc_meetings(year_endpoint):
    url = urljoin(BASE_CADC_URL, year_endpoint)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    meetings = []

    # CADC formats meetings as list items or entries with external links
    for item in soup.find_all(["li", "div"]):
        text = item.get_text(separator=" ", strip=True)
        links = item.find_all("a", href=True)
        external_links = [
            a["href"] for a in links
            if a["href"].startswith("http") and "cadc-ccda" not in a["href"] and "canada.ca" not in a["href"]
        ]
        if external_links and len(text) > 40:
            meetings.append({
                "text": text,
                "url": external_links[0],
                "endpoint": year_endpoint
            })
    return meetings

def check_meeting_website(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        text = resp.text.lower()

        # Check for financial & accommodation support keywords
        support_terms = [
            "travel grant", "travel support", "financial support",
            "student grant", "bursary", "fee waiver", "accommodation covered",
            "lodging provided", "iau grant", "fellowship"
        ]
        found_support = [term for term in support_terms if term in text]

        # Look for abstract submission deadline dates
        deadline_match = re.search(
            r"abstract[^\n\.\<]{0,50}(deadline|due|by)?:?\s*([A-Za-z]+\s+\d{1,2},?\s*\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})",
            text,
            re.IGNORECASE
        )
        deadline = deadline_match.group(2) if deadline_match else "Check website directly"

        return {
            "has_support": len(found_support) > 0,
            "support_details": ", ".join(found_support) if found_support else "None detected",
            "deadline": deadline
        }
    except Exception:
        return {
            "has_support": False,
            "support_details": "Website unreachable",
            "deadline": "Check website directly"
        }

def main():
    config = load_config()
    keywords = [kw.lower() for kw in config.get("keywords", [])]

    history_file = "seen_meetings.json"
    seen = json.load(open(history_file)) if os.path.exists(history_file) else []

    matched_meetings = []
    for endpoint in config.get("check_years", ["this-year", "next-year"]):
        meetings = get_cadc_meetings(endpoint)
        for m in meetings:
            if m["url"] in seen:
                continue
            # Check if any keyword appears in the meeting entry text
            if any(kw in m["text"].lower() for kw in keywords):
                analysis = check_meeting_website(m["url"])
                m.update(analysis)
                matched_meetings.append(m)
                seen.append(m["url"])

    with open(history_file, "w") as f:
        json.dump(seen, f, indent=2)

    if matched_meetings:
        with open("digest.md", "w") as f:
            f.write("### 🔭 Newly Detected Astronomy Meetings\n\n")
            for m in matched_meetings:
                f.write(f"#### [{m['url']}]({m['url']})\n")
                f.write(f"- **Abstract Deadline**: {m['deadline']}\n")
                f.write(f"- **Travel/Lodging Support**: {'✅ **Yes** (' + m['support_details'] + ')' if m['has_support'] else '❓ Not detected'}\n")
                f.write(f"- **CADC Listing Summary**: {m['text'][:280]}...\n\n")
        print(f"Found {len(matched_meetings)} new matching meetings.")
    else:
        print("No new matching meetings found.")

if __name__ == "__main__":
    main()
