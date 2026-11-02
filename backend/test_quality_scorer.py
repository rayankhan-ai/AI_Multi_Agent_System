# Import the quality scoring function.
from backend.agents.quality_scorer import quality_scorer_agent


# Create sample research data without making an API request.
sample_state = {
    "research_question": (
        "How do multi-agent AI systems improve research automation?"
    ),

    "search_results": [
        {
            "title": "Research Source One",
            "url": "https://example.com/source-one",
            "content": "This is useful research content. " * 10,
        },
        {
            "title": "Research Source Two",
            "url": "https://example.com/source-two",
            "content": "This is another useful source. " * 10,
        },
        {
            "title": "Research Source Three",
            "url": "https://example.com/source-three",
            "content": "This source provides additional evidence. " * 10,
        },
        {
            "title": "Research Source Four",
            "url": "https://example.com/source-four",
            "content": "This source contains further information. " * 10,
        },
        {
            "title": "Research Source Five",
            "url": "https://example.com/source-five",
            "content": "This source provides another useful perspective. " * 10,
        },
    ],

    "analysis": (
        "This is a sample research analysis containing more than "
        "200 characters. It examines how multiple AI agents can "
        "divide research tasks, collect information, analyze evidence, "
        "and review findings before producing a report."
    ),

    "fact_check": (
        "The available evidence supports some of the main findings. "
        "However, each important claim should be compared with the "
        "original sources, and source independence should be examined."
    ),

    "activity_log": ["Test workflow initialized."],
}


# Run the quality scorer.
result = quality_scorer_agent(sample_state)


# Display the results.
print("=" * 60)
print("RESEARCH QUALITY SCORING TEST")
print("=" * 60)

print(f"Quality Score: {result['quality_score']}/100")
print(f"Feedback: {result['quality_feedback']}")

print("\nQUALITY DETAILS")

for check_name, check_details in result["quality_details"].items():
    print(f"\n{check_name}:")
    print(check_details)

print("\nACTIVITY LOG")

for activity in result["activity_log"]:
    print(f"- {activity}")


# Verify that the score and details are valid.
assert 0 <= result["quality_score"] <= 100
assert len(result["quality_details"]) == 5
assert result["quality_feedback"]
assert len(result["activity_log"]) >= 2

print("\nSUCCESS: Quality scoring tests passed.")