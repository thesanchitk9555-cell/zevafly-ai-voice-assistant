import os
import logging
from fastapi import FastAPI, Request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
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

# मल्टी-मॉडल फॉलबैक लिस्ट
MODELS_LIST = [
    'gemini-3.6-flash',
    'gemini-3.5-flash-lite',
    'gemini-3.1-flash-lite',
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'antigravity'
]

# ट्विलियो (कॉल और WhatsApp के लिए)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None

SIYA_SYSTEM_PROMPT = """
You are Siya, a professional, warm, and highly intelligent personal AI assistant to Sanjit, the founder of Zevafly.
Your behavior:
1. Talk like a real human being, naturally, politely, and conversationally. Never sound like a robot.
2. Support any language the user speaks (Hindi, Hinglish, English) and reply fluently in that exact same language.
3. Answer inquiries about Zevafly, assist callers or chat users, and collect project or lead details.
4. Keep responses concise, clear, and engaging.
"""

def generate_with_fallback(contents: str, system_instruction: str):
    """फॉलबैक फंक्शन: एक मॉडल फेल होने पर दूसरे मॉडल से रिस्पॉन्स जनरेट करता है।"""
    for model_name in MODELS_LIST:
        try:
            logger.info(f"Attempting generation with model: {model_name}")
            chat_completion = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=150,
                    temperature=0.7,
                ),
            )
            if chat_completion and chat_completion.text:
                return chat_completion.text.strip()
        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}. Trying next...")
            continue
    return None

@app.get("/")
def home():
    return {"status": "Siya AI Assistant (WhatsApp + Voice) is active!"}

# ==========================================
# 1. फोन कॉल राउट
# ==========================================
@app.post("/voice")
async def handle_incoming_call(request: Request):
    logger.info("Outgoing call connected.")
    response = VoiceResponse()
    
    gather = Gather(
        input="speech",
        action="/process-speech",
        method="POST",
        speech_timeout="auto",
        language="hi-IN"
    )
    gather.say(
        "नमस्ते! मैं सिया हूँ, ज़ेवलाफ के फाउंडर संजित की पर्सनल असिस्टेंट। बताइए, मैं आपकी क्या मदद कर सकती हूँ?",
        voice="alice"
    )
    response.append(gather)
    response.redirect("/voice")
    return Response(content=str(response), media_type="application/xml")

@app.post("/process-speech")
async def process_speech(request: Request):
    form_data = await request.form()
    user_speech = form_data.get("SpeechResult", "").strip()
    logger.info(f"Caller said: {user_speech}")

    response = VoiceResponse()

    if not user_speech:
        gather = Gather(input="speech", action="/process-speech", method="POST", speech_timeout="auto")
        gather.say("क्षमा करें, मैंने आपकी बात ठीक से सुनी नहीं। क्या आप दोबारा दोहरा सकते हैं?", voice="alice")
        response.append(gather)
        return Response(content=str(response), media_type="application/xml")

    try:
        ai_reply = generate_with_fallback(user_speech, SIYA_SYSTEM_PROMPT)
        if not ai_reply:
            ai_reply = "क्षमा करें, अभी सभी मॉडल्स की लिमिट पूरी हो चुकी है।"
        
        logger.info(f"Siya Voice replied: {ai_reply}")

    except Exception as e:
        logger.error(f"Error in Voice processing: {e}")
        ai_reply = "अभी थोड़ा नेटवर्क इशू है, मैं एक मिनट में आपसे दोबारा जुड़ती हूँ।"

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
# 2. WhatsApp चैट राउट
# ==========================================
@app.post("/whatsapp")
async def whatsapp_reply(request: Request):
    try:
        form_data = await request.form()
        incoming_msg = form_data.get("Body", "").strip()
        sender_number = form_data.get("From", "")
        logger.info(f"WhatsApp User ({sender_number}) said: {incoming_msg}")

        if not incoming_msg:
            ai_reply = "नमस्ते! मैं सिया हूँ, ज़ेवलाफ से। बताइए, मैं आपकी क्या मदद कर सकती हूँ?"
        else:
            lower_msg = incoming_msg.lower()
            # कॉल कमांड चेक करें
            if "call karo" in lower_msg or "mujhe call" in lower_msg or "call lagao" in lower_msg:
                phone_to_call = sender_number.replace("whatsapp:", "").strip()
                if twilio_client and TWILIO_PHONE_NUMBER:
                    # आउटगोइंग कॉल राउटिंग
                    twilio_client.calls.create(
                        to=phone_to_call,
                        from_=TWILIO_PHONE_NUMBER,
                        url='https://zevafly-ai.onrender.com/voice'
                    )
                    ai_reply = "मैंने आपके नंबर पर फोन कॉल मिला दिया है, कृपया अपना फोन उठाइए! (नोट: कॉल उठते ही अपने फोन कीपैड का कोई भी 1 बटन जरूर दबाएं)"
                else:
                    ai_reply = "माफ कीजिए, कॉल करने के लिए Twilio सेटअप नहीं है।"
            else:
                # नॉर्मल मैसेज का रिप्लाई
                ai_reply = generate_with_fallback(incoming_msg, SIYA_SYSTEM_PROMPT)
                if not ai_reply:
                    ai_reply = "क्षमा करें, अभी एआई की डेली लिमिट पूरी हो चुकी है।"
                logger.info(f"Siya WhatsApp replied: {ai_reply}")

    except Exception as e:
        logger.error(f"Error in WhatsApp processing: {e}")
        ai_reply = "क्षमा करें, अभी तकनीकी समस्या के कारण मैं तुरंत जवाब नहीं दे पा रही हूँ।"

    twilio_resp = MessagingResponse()
    twilio_resp.message(ai_reply)
    return Response(content=str(twilio_resp), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
