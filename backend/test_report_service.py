# ============================================================
# PROJECT 4 - AI MULTI-AGENT RESEARCH & AUTOMATION SYSTEM
# PART 10 - TEST REPORT SAVING
# ============================================================

# Import the report-saving function.
from backend.services.report_service import save_research_report


def test_report_saving():
    """
    Test saving a sample Markdown research report.
    """

    # Create a sample report without making an AI API call.
    sample_report = """
# Example AI Research Report

## Executive Summary

This is a sample report used to test the report-saving service.

## Key Findings

- The report-saving function creates Markdown files.
- Reports are stored in the project's reports directory.
- UTF-8 encoding is used to preserve text.

## Conclusion

The report-saving service should save this content successfully.
"""

    # Save the sample report.
    result = save_research_report(
        report_content=sample_report,
        title="Example AI Research Report",
    )

    # Display the result.
    print("\n" + "=" * 60)
    print("REPORT SAVING TEST")
    print("=" * 60)

    print("Success:", result["success"])
    print("Message:", result["message"])

    if result["success"]:
        print("Filename:", result["filename"])
        print("Saved path:", result["file_path"])

        # Confirm that the file exists.
        from pathlib import Path

        saved_file = Path(result["file_path"])

        if saved_file.exists():
            print("\nSUCCESS: The report file exists.")
            print("File size:", saved_file.stat().st_size, "bytes")
        else:
            print("\nERROR: The report file was not found.")

    else:
        print("\nERROR: The report could not be saved.")


# Run the test when this file is executed directly.
if __name__ == "__main__":
    test_report_saving()
