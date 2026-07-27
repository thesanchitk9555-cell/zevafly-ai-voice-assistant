import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
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
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# जीमेल क्रेडेंशियल्स
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")

# सिया का सिस्टम प्रॉम्प्ट (पर्सना और निर्देश)
SIYA_SYSTEM_PROMPT = """
You are Siya, the professional and intelligent personal AI assistant to Sanchit, the founder of Zevafly.
Your tasks:
1. Handle incoming calls and messages professionally, supporting any language the user speaks and replying fluently in that exact same language.
2. Answer inquiries about Zevafly and collect user project/lead details (Name, requirement, phone number, etc.).
3. Keep responses conversational, natural, and concise, suitable for chat and phone calls.
"""

def send_call_summary_email(user_speech: str, ai_reply: str):
    """
    कॉल और बातचीत का विवरण जीमेल पर भेजने का फंक्शन।
    """
    if not SENDER_EMAIL or not EMAIL_APP_PASSWORD or not RECEIVER_EMAIL:
        logger.warning("Email credentials not configured properly.")
        return

    try:
        subject = "📞 New Update from Siya - Zevafly"
        body = f"""
        Boss Sanchit,
        
        Siya ki ek nayi baat complete hui hai. Yahan uska vivaran hai:
        
        - Customer ne kya kaha: {user_speech}
        - Siya ne kya jawab diya: {ai_reply}
        
        Aapka AI Assistant,
        Siya (Zevafly)
        """

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Gmail SMTP Server के जरिए सिक्योर मेल भेजना
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, EMAIL_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            
        logger.info("Summary email sent successfully!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

@app.get("/")
def home():
    return {"status": "Siya is active, multilingual, and connected with Gmail!"}

@app.post("/voice")
async def handle_incoming_call(request: Request):
    """
    कॉल आने पर सिया की पहली ग्रीटिंग्स।
    """
    logger.info("Incoming call received.")
    response = VoiceResponse()
    
    gather = Gather(
        input="speech",
        action="/process-speech",
        method="POST",
        speech_timeout="auto",
        language="hi-IN"
    )
    gather.say(
        "Hello, I am Siya, personal assistant to Sanchit, founder of Zevafly. "
        "Namaste, main Zevafly ke founder Sanchit ki personal assistant Siya hoon. "
        "Aap batayiye, main aapki kya madad kar sakti hoon?",
        voice="alice"
    )
    response.append(gather)
    response.redirect("/voice")
    return Response(content=str(response), media_type="application/xml")

@app.post("/process-speech")
async def process_speech(request: Request):
    """
    यूजर की बात सुनकर जेमिनी से जवाब जनरेट करना और जीमेल पर अपडेट भेजना।
    """
    form_data = await request.form()
    user_speech = form_data.get("SpeechResult", "")
    logger.info(f"User said: {user_speech}")

    response = VoiceResponse()

    if not user_speech:
        gather = Gather(input="speech", action="/process-speech", method="POST", speech_timeout="auto")
        gather.say("I didn't catch that. Could you please repeat?", voice="alice")
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    try:
        chat_completion = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=user_speech,
            config=types.GenerateContentConfig(
                system_instruction=SIYA_SYSTEM_PROMPT,
                max_output_tokens=150,
                temperature=0.7,
            ),
        )
        ai_reply = chat_completion.text.strip()
        logger.info(f"Siya replied: {ai_reply}")

        send_call_summary_email(user_speech, ai_reply)

    except Exception as e:
        logger.error(f"Error communicating with Gemini API: {e}")
        ai_reply = "I am having a little trouble connecting right now. Please give us a moment."

    gather = Gather(
        input="speech",
        action="/process-speech",
        method="POST",
        speech_timeout="auto"
    )
    gather.say(ai_reply, voice="alice")
    response.append(gather)
    
    return Response(content=str(response), media_type="application/xml")


# ==========================================
# WhatsApp चैट के लिए नया राउट (Route)
# ==========================================
@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    form_data = await request.form()
    incoming_msg = form_data.get("Body", "").strip()
    logger.info(f"WhatsApp User said: {incoming_msg}")

    try:
        chat_completion = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=incoming_msg,
            config=types.GenerateContentConfig(
                system_instruction=SIYA_SYSTEM_PROMPT,
                max_output_tokens=150,
                temperature=0.7,
            ),
        )
        ai_reply = chat_completion.text.strip()
        logger.info(f"Siya WhatsApp replied: {ai_reply}")

        # चाहें तो व्हाट्सएप चैट का अपडेट भी जीमेल पर भेज सकते हैं
        send_call_summary_email(incoming_msg, ai_reply)

    except Exception as e:
        logger.error(f"Error in WhatsApp Gemini API: {e}")
        ai_reply = "क्षमा करें, अभी तकनीकी समस्या के कारण मैं जवाब नहीं दे पा रही हूँ।"

    twilio_resp = MessagingResponse()
    twilio_resp.message(ai_reply)
    
    return Response(content=str(twilio_resp), media_type="application/xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
