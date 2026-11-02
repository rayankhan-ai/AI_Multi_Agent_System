# Import os to read environment variables.
import os

# Import the Groq client.
from groq import Groq

# Import load_dotenv to load settings from the project .env file.
from dotenv import load_dotenv

# Import the exception class for handling API errors.
from groq import APIError


# Load environment variables from the project root.
load_dotenv()


def test_groq_connection():
    """Send a simple question to Groq and print the response."""

    # Read the API key without printing it.
    api_key = os.getenv("GROQ_API_KEY")

    # Read the model name from the environment, with a default value.
    model_name = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

    # Stop if the API key is missing or still contains the placeholder.
    if not api_key or "PASTE_YOUR" in api_key:
        print("ERROR: GROQ_API_KEY is missing.")
        print("Add your actual Groq API key to the project's .env file.")
        return

    try:
        # Create the Groq client using the private API key.
        client = Groq(api_key=api_key)

        print("Sending a test question to Groq...")
        print(f"Model: {model_name}")

        # Send a short request to the selected language model.
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful AI assistant. "
                        "Answer clearly and briefly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "In two sentences, explain what an AI agent is."
                    ),
                },
            ],
            temperature=0.2,
            max_completion_tokens=250,
        )

        # Extract the generated text from the API response.
        answer = response.choices[0].message.content

        print("\nSUCCESS: Groq connection is working.")
        print("\nModel response:")
        print(answer)

    except APIError as error:
        # Print the API error without displaying the API key.
        print("\nGroq API request failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Details: {error}")

        print(
            "\nCheck your API key, model availability, "
            "account limits, and API permissions."
        )

    except Exception as error:
        # Handle other problems such as connectivity issues.
        print("\nAn unexpected error occurred.")
        print(f"Error type: {type(error).__name__}")
        print(f"Details: {error}")


# Run the test when this file is executed directly.
if __name__ == "__main__":
    test_groq_connection()
