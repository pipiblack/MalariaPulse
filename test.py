from google import genai

from malariapulse.ai import get_gemini_api_key


api_key = get_gemini_api_key()
if not api_key:
    raise RuntimeError("Add GEMINI_API_KEY to .env.local before running this test.")

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents="Say 'API key is working!' if you can read this.",
    )
    print("Success! Response from Gemini:")
    print(response.text.strip())
except Exception as error:
    print(f"Error testing API key: {error}")
