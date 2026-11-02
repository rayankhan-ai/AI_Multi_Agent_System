# Import the types needed to read and update research state.
from typing import Any, Dict

# Import the shared state definition.
from backend.graph.state import ResearchState


def quality_scorer_agent(state: ResearchState) -> Dict[str, Any]:
    """
    Evaluate research quality using transparent, rule-based checks.

    The score is based on source quantity, source content,
    analysis availability, and fact-checking availability.

    This is a heuristic score, not a factual accuracy guarantee.
    """

    # Read validated research sources from the shared state.
    sources = state.get("search_results", [])

    # Read the analysis produced by the Analyst Agent.
    analysis = state.get("analysis", "").strip()

    # Read the fact-checking result.
    fact_check = state.get("fact_check", "").strip()

    # Read the original research question.
    question = state.get("research_question", "").strip()

    # Record each quality check and its score.
    details: Dict[str, Any] = {}

    # Start with a score of zero.
    score = 0

    # ---------------------------------------------------------
    # Check 1: Valid source quantity — maximum 30 points.
    # ---------------------------------------------------------

    # More independent sources generally provide broader evidence.
    source_count = len(sources)

    if source_count >= 8:
        source_score = 30
    elif source_count >= 5:
        source_score = 25
    elif source_count >= 3:
        source_score = 20
    elif source_count >= 1:
        source_score = 10
    else:
        source_score = 0

    score += source_score

    details["source_quantity"] = {
        "valid_source_count": source_count,
        "score": source_score,
        "maximum_score": 30,
    }

    # ---------------------------------------------------------
    # Check 2: Source content quality — maximum 20 points.
    # ---------------------------------------------------------

    # Check whether sources contain meaningful text.
    sources_with_content = sum(
        1
        for source in sources
        if isinstance(source, dict)
        and len(str(source.get("content", "")).strip()) >= 100
    )

    # Calculate the percentage of sources with useful content.
    if source_count > 0:
        content_ratio = sources_with_content / source_count
    else:
        content_ratio = 0

    # Award points according to the percentage of useful sources.
    content_score = round(content_ratio * 20)

    score += content_score

    details["source_content"] = {
        "sources_with_useful_content": sources_with_content,
        "total_sources": source_count,
        "score": content_score,
        "maximum_score": 20,
    }

    # ---------------------------------------------------------
    # Check 3: Research analysis — maximum 25 points.
    # ---------------------------------------------------------

    # A nonempty analysis is required for a meaningful report.
    if len(analysis) >= 500:
        analysis_score = 25
    elif len(analysis) >= 200:
        analysis_score = 20
    elif len(analysis) >= 50:
        analysis_score = 10
    else:
        analysis_score = 0

    score += analysis_score

    details["analysis"] = {
        "analysis_characters": len(analysis),
        "score": analysis_score,
        "maximum_score": 25,
    }

    # ---------------------------------------------------------
    # Check 4: Fact-checking — maximum 15 points.
    # ---------------------------------------------------------

    # Award points when the Fact-Checker Agent returns a result.
    if len(fact_check) >= 200:
        fact_check_score = 15
    elif len(fact_check) >= 50:
        fact_check_score = 10
    elif fact_check:
        fact_check_score = 5
    else:
        fact_check_score = 0

    score += fact_check_score

    details["fact_checking"] = {
        "fact_check_characters": len(fact_check),
        "score": fact_check_score,
        "maximum_score": 15,
    }

    # ---------------------------------------------------------
    # Check 5: Research question — maximum 10 points.
    # ---------------------------------------------------------

    # Check whether the original question is available.
    question_score = 10 if len(question) >= 10 else 0

    score += question_score

    details["research_question"] = {
        "question_available": bool(question),
        "score": question_score,
        "maximum_score": 10,
    }

    # Keep the score within the permitted range.
    score = max(0, min(100, score))

    # Generate readable feedback from the overall score.
    if score >= 85:
        feedback = (
            "Strong research structure. Review the cited evidence "
            "and source independence before relying on the conclusions."
        )
    elif score >= 70:
        feedback = (
            "Good research structure, but some areas may need "
            "additional evidence or deeper analysis."
        )
    elif score >= 50:
        feedback = (
            "Moderate research quality. Consider collecting more "
            "useful sources and improving the analysis or fact-check."
        )
    else:
        feedback = (
            "Research quality needs improvement. Check source availability, "
            "analysis completeness, and fact-checking results."
        )

    # Add a clear explanation to the workflow activity log.
    activity_log = list(state.get("activity_log", []))
    activity_log.append(
        f"Quality Scoring Agent calculated a research quality score of {score}/100."
    )

    # Return the new values to the shared workflow state.
    return {
        "quality_score": score,
        "quality_feedback": feedback,
        "quality_details": details,
        "activity_log": activity_log,
    }