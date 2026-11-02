# ============================================================
# PROJECT 4 - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# PART 12 - SOURCE VALIDATOR TESTS
# ============================================================

# Import the function we want to test.
from backend.services.source_validator import validate_research_sources


def test_source_validation():

    # Create sample search results for testing.
    sample_sources = [
        {
            "title": "Introduction to Multi-Agent AI",
            "url": "https://example.com/multi-agent-ai",
            "content": (
                "Multi-agent AI systems use multiple specialized agents "
                "to collaborate on tasks, share information, and solve "
                "complex problems through coordinated interactions."
            ),
        },
        {
            "title": "Second Research Source",
            "url": "https://example.org/research",
            "content": (
                "Research systems can use different agents for planning, "
                "information retrieval, analysis, and verification. "
                "Each stage contributes to the final research output."
            ),
        },
        {
            # This result should be rejected because its title is empty.
            "title": "",
            "url": "https://example.net/missing-title",
            "content": (
                "This source contains enough text, but it does not have "
                "a title and therefore should not be accepted."
            ),
        },
        {
            # This result should be rejected because its URL is invalid.
            "title": "Invalid URL Example",
            "url": "not-a-valid-web-url",
            "content": (
                "This result has a title and content, but its URL is "
                "not a supported HTTP or HTTPS address."
            ),
        },
        {
            # This result should be rejected because its content is too short.
            "title": "Short Content Example",
            "url": "https://example.com/short",
            "content": "Too short.",
        },
        {
            # This result should be rejected as a duplicate URL.
            "title": "Duplicate Research Source",
            "url": "https://example.com/multi-agent-ai/",
            "content": (
                "This source uses a URL that duplicates the first result "
                "after the validator removes trailing slashes."
            ),
        },
    ]

    # Validate all the sample sources.
    result = validate_research_sources(sample_sources)

    # Display the test results.
    print("\n" + "=" * 60)
    print("SOURCE VALIDATION TEST")
    print("=" * 60)

    print("Total sources:", result["total_sources"])
    print("Accepted sources:", result["accepted_count"])
    print("Rejected sources:", result["rejected_count"])

    print("\nAccepted source titles:")

    for source in result["valid_sources"]:
        print("-", source["title"])

    print("\nRejected sources:")

    for source in result["rejected_sources"]:
        print(
            f"- Source {source['source']}: "
            f"{source['reason']}"
        )

    # Confirm the expected results.
    assert result["total_sources"] == 6
    assert result["accepted_count"] == 2
    assert result["rejected_count"] == 4

    # Confirm that the first valid source was preserved.
    assert (
        result["valid_sources"][0]["title"]
        == "Introduction to Multi-Agent AI"
    )

    print("\nSUCCESS: Source validation tests passed.")


if __name__ == "__main__":
    test_source_validation()
