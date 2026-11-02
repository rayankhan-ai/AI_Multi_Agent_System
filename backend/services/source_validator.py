# ============================================================
# PROJECT 4 - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# PART 12 - SOURCE VALIDATION SERVICE
# ============================================================

# Import URL parsing tools to check the structure of source URLs.
from urllib.parse import urlparse

# Import typing helpers for readable function inputs and outputs.
from typing import Any, Dict, List


def validate_research_sources(
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Validate and deduplicate web research sources.

    A source is accepted when it has:
    1. A non-empty title.
    2. A valid HTTP or HTTPS URL with a hostname.
    3. Meaningful textual content.

    Duplicate URLs are rejected after normalizing their basic form.
    """

    # Keep validated sources separately from rejected sources.
    valid_sources: List[Dict[str, Any]] = []
    rejected_sources: List[Dict[str, str]] = []

    # Store normalized URLs so we can detect duplicates.
    seen_urls = set()

    # Examine each source returned by the search provider.
    for index, source in enumerate(sources, start=1):

        # Reject results that are not dictionaries.
        if not isinstance(source, dict):
            rejected_sources.append({
                "source": str(index),
                "reason": "Source result is not a dictionary.",
            })
            continue

        # Read the important fields and safely convert them to strings.
        title = str(source.get("title") or "").strip()
        url = str(source.get("url") or "").strip()
        content = str(source.get("content") or "").strip()

        # Reject sources without a title.
        if not title:
            rejected_sources.append({
                "source": str(index),
                "reason": "Source title is missing.",
            })
            continue

        # Parse the URL to inspect its structure.
        parsed_url = urlparse(url)

        # Accept only HTTP or HTTPS URLs with a hostname.
        if (
            parsed_url.scheme.lower() not in ("http", "https")
            or not parsed_url.hostname
        ):
            rejected_sources.append({
                "source": str(index),
                "reason": "Source URL is invalid or unsupported.",
            })
            continue

        # Reject empty or extremely short content.
        if len(content) < 40:
            rejected_sources.append({
                "source": str(index),
                "reason": "Source content is missing or too short.",
            })
            continue

        # Normalize the URL for duplicate detection.
        normalized_url = url.rstrip("/").lower()

        # Reject URLs already accepted earlier in the collection.
        if normalized_url in seen_urls:
            rejected_sources.append({
                "source": str(index),
                "reason": "Duplicate source URL.",
            })
            continue

        # Remember this URL so duplicates can be identified.
        seen_urls.add(normalized_url)

        # Preserve the original source information.
        valid_sources.append(source)

    # Return the validated results and useful statistics.
    return {
        "valid_sources": valid_sources,
        "rejected_sources": rejected_sources,
        "total_sources": len(sources),
        "accepted_count": len(valid_sources),
        "rejected_count": len(rejected_sources),
    }
