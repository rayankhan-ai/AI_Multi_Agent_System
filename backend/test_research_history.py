# ============================================================
# PART 16 - RESEARCH HISTORY SERVICE TEST
# ============================================================

# Import functions from the Research History Service.
from backend.services.research_history import (
    create_research_metadata,
    save_research_metadata,
)


def main():
    # Define a sample research question.
    question = (
        "How can multi-agent AI systems automate research?"
    )

    # Generate metadata for this research run.
    metadata = create_research_metadata(question)

    # Display the generated metadata.
    print("=" * 60)
    print("RESEARCH HISTORY TEST")
    print("=" * 60)

    print("Research ID:", metadata["research_id"])
    print("Research Timestamp:", metadata["research_timestamp"])
    print("Research Question:", metadata["research_question"])

    # Save sample metadata next to a hypothetical report.
    result = save_research_metadata(
        metadata=metadata,
        report_filename="sample_research_report.md",
        quality_score=85,
        total_sources=10,
        accepted_sources=8,
        rejected_sources=2,
    )

    # Display the saving result.
    print("\nMETADATA SAVE RESULT")
    print("Success:", result["success"])
    print("Filename:", result["metadata_filename"])
    print("Path:", result["metadata_path"])

    # Verify that the metadata was saved successfully.
    assert result["success"] is True
    assert result["metadata"]["quality_score"] == 85
    assert result["metadata"]["source_statistics"]["total_sources"] == 10
    assert result["metadata"]["source_statistics"]["accepted_sources"] == 8
    assert result["metadata"]["source_statistics"]["rejected_sources"] == 2

    print("\nSUCCESS: Research history tests passed.")


if __name__ == "__main__":
    main()
