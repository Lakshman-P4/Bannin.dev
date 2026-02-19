import os
import google.generativeai as genai

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    key = input("Paste your Gemini API key: ").strip()

genai.configure(api_key=key)
try:
    response = genai.GenerativeModel("gemini-2.0-flash-lite").generate_content("Say hello")
    print("SUCCESS:", response.text)
except Exception as e:
    print("FAILED:", e)
