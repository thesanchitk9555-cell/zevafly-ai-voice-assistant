import os
import logging
from fastapi import FastAPI, Request, Response
from twilio.twiml.messaging_response import MessagingResponse
from google import genai
from google.genai import types
from dotenv import load_dotenv

# एनवायरनमेंट वेरिएबल्स लोड करें
load_dotenv()

# लॉगिंग सेट अप करें
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Siya - Zevafly AI Assistant")

# जेमिनी क्लाइंट इनिशियलाइज करें
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# सिया का सरल और सीधा सिस्टम प्रॉम्प्ट
SIYA_SYSTEM_PROMPT = """
You are Siya, a friendly and intelligent personal AI assistant to Sanjit, the founder of Zevafly.
Instructions:
1. Reply naturally, politely, and concisely in Hinglish or the exact language the user speaks.
2. Never output bullet points, options, or extra formatting. Just reply with plain conversational text.
"""

@app.get("/")
def home():
    return {"status": "Siya is active and running smoothly!"}

# ==========================================
# WhatsApp चैट के लिए राउट (Route)
# ==========================================
@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    try:
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        logger.info(f"WhatsApp User said: {incoming_msg}")

        if not incoming_msg:
            ai_reply = "Hello! Main Siya hoon, aapki kya madad kar sakti hoon?"
        else:
            chat_completion = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=incoming_msg,
                config=types.GenerateContentConfig(
                    system_instruction=SIYA_SYSTEM_PROMPT,
                    max_output_tokens=150,
                    temperature=0.7,
                ),
            )
            ai_reply = chat_completion.text.strip()
            logger.info(f"Siya WhatsApp replied: {ai_reply}")

    except Exception as e:
        logger.error(f"Error in WhatsApp Gemini API: {e}")
        ai_reply = "Hey! Abhi thodi technical problem hai, main thodi der mein baat karti hoon."

    # Twilio Messaging Response भेजना
    twilio_resp = MessagingResponse()
    twilio_resp.message(ai_reply)
    
    return Response(content=str(twilio_resp), media_type="application/xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
