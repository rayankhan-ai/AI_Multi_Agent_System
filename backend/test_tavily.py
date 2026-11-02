# Import os to read the Tavily API key.
import os

# Import the Tavily client.
from tavily import TavilyClient

# Import load_dotenv to load the project's environment variables.
from dotenv import load_dotenv


# Load variables from the project's .env file.
load_dotenv()


def test_tavily_connection():
    """Search the web and display a few results."""

    # Read the private Tavily API key.
    api_key = os.getenv("TAVILY_API_KEY")

    # Stop if the API key is missing or still contains the placeholder.
    if not api_key or "PASTE_YOUR" in api_key:
        print("ERROR: TAVILY_API_KEY is missing.")
        print("Add your actual Tavily API key to the .env file.")
        return

    try:
        # Create the Tavily client.
        client = TavilyClient(api_key=api_key)

        # Define a simple research question.
        query = "What is a multi-agent AI system?"

        print("Searching the web with Tavily...")
        print(f"Query: {query}")

        # Search for relevant web pages.
        response = client.search(
            query=query,
            max_results=3,
        )

        # Retrieve the search results from the response.
        results = response.get("results", [])

        if not results:
            print("\nThe search completed, but no results were returned.")
            return

        print("\nSUCCESS: Tavily web search is working.")
        print(f"Number of results: {len(results)}")

        # Display the title, URL, and a short excerpt for each result.
        for index, result in enumerate(results, start=1):
            print(f"\nResult {index}")

            print(
                "Title:",
                result.get("title", "No title available"),
            )

            print(
                "URL:",
                result.get("url", "No URL available"),
            )

            content = result.get("content", "")
            print("Content:", content[:300])

    except Exception as error:
        # Display diagnostic information without printing the API key.
        print("\nTavily search failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Details: {error}")

        print(
            "\nCheck your API key, account limits, "
            "network connection, and Tavily API availability."
        )


# Execute the test when this file is run directly.
if __name__ == "__main__":
    test_tavily_connection()
