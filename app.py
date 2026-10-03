from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Token proporcionado
TOKEN = "8896533030:AAFquO47wLBEphyUGoWLiLfneq5VEuy7eN8"

# URL pública de tu backend (ej. ngrok, Render, Railway, etc.)
WEB_APP_URL = "https://tu-dominio-o-ngrok.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Crear un botón que abre la Mini App de Telegram
    keyboard = [
        [InlineKeyboardButton("⚡ Abrir Tactical Matrix OSINT", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"Saludos, **{user.first_name}**.\n\n"
        "Terminal de Inteligencia Táctica conectada exitosamente a la nube.\n"
        "Haz clic abajo para desplegar la interfaz operativa.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Manejador del comando /start
    app.add_handler(CommandHandler("start", start))
    
    print("[+] Bot de Telegram iniciado correctamente y escuchando comandos...")
    app.run_polling()

if __name__ == "__main__":
    main()
    
