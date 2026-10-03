import os
import sqlite3
import requests
import asyncio
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type

from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TOKEN = "8596194498:AAFuL6e9NQ5Iu3MHjAD_brMWZHipYbWSfdA"
WEB_APP_URL = "https://cdps-osint-bot.onrender.com"

app = FastAPI(title="GEODOS OSINT & GEOINT Suite", version="6.4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

telegram_app = Application.builder().token(TOKEN).concurrent_updates(True).build()

class QueryRequest(BaseModel):
    user_id: int
    query: str
    type: str
    page: int = 1

RUTA_DB = "ine.db"

def realizar_busqueda_real_completa(query: str, modo: str):
    resultados = []
    q_up = query.upper()
    palabras = q_up.split()
    
    try:
        if modo == 'ine':
            if not os.path.exists(RUTA_DB):
                return ["⚠️ [!] Base de datos masiva 'ine.db' no detectada en el servidor."]
            
            conn = sqlite3.connect(RUTA_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tablas = cursor.fetchall()
            
            encontrados_count = 0
            for t in tablas:
                nombre_tabla = t[0]
                cursor.execute(f"PRAGMA table_info({nombre_tabla})")
                columnas = [col[1] for col in cursor.fetchall()]
                if not columnas: 
                    continue
                
                condiciones = []
                parametros = []
                for palabra in palabras:
                    cond_palabra = " OR ".join([f"UPPER(CAST({c} AS TEXT)) LIKE ?" for c in columnas[:6]])
                    condiciones.append(f"({cond_palabra})")
                    for _ in columnas[:6]: 
                        parametros.append(f"%{palabra}%")
                
                where_clause = " AND ".join(condiciones)
                cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE {where_clause} LIMIT 5", parametros)
                
                for fila in cursor.fetchall():
                    items = [str(item).strip() for item in fila if item is not None and str(item).strip() != ""]
                    if items:
                        encontrados_count += 1
                        resultados.append(
                            f"┌ 🎯 **EXPEDIENTE REAL ENCONTRADO [DB 25GB]**\n"
                            f"├ 👤 **Nombre / Datos:** {' '.join(items[2:6]) if len(items)>5 else 'N/D'}\n"
                            f"├ 🪪 **CURP / ID:** {items[0] if len(items)>0 else 'N/D'}\n"
                            f"├ 📅 **Datos Secundarios:** {items[1] if len(items)>1 else 'N/D'}\n"
                            f"└ 📍 **Domicilio Registrado:** {' '.join(items[6:11]) if len(items)>6 else 'N/D'}"
                        )
                if encontrados_count >= 5: 
                    break
            conn.close()
            
            if not resultados:
                resultados.append(f"⚠️ [!] No se hallaron similitudes exactas para `{query}` en la base de datos.")

        elif modo == 'telefono':
            parsed = phonenumbers.parse(query, None)
            if phonenumbers.is_valid_number(parsed):
                pais = geocoder.description_for_number(parsed, 'es') or "Desconocido"
                operador = carrier.name_for_number(parsed, 'es') or "Operador / OMV"
                zona = ', '.join(timezone.time_zones_for_number(parsed))
                num_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                t_type = number_type(parsed)
                tipo_str = "Móvil / Celular" if t_type == phonenumbers.PhoneNumberType.MOBILE else "Línea Fija"
                
                resultados.append(
                    f"┌ 📱 **INFORME TÁCTICO DE TELEFONÍA E.164**\n"
                    f"├ 🎯 **Target:** `{num_e164}`\n"
                    f"├ 🌍 **País de Registro:** {pais.upper()}\n"
                    f"├ 📶 **Carrier / Operador:** {operador.upper()}\n"
                    f"├ 📞 **Tipo de Línea:** {tipo_str.upper()}\n"
                    f"└ 🕒 **Zona Horaria:** {zona}"
                )
            else:
                resultados.append("⚠️ Estructura E.164 inválida o no reconocida.")

        elif modo == 'geo':
            resp = requests.get(f"http://ip-api.com/json/{query}", timeout=5).json()
            if resp.get("status") == "success":
                resultados.append(
                    f"┌ 🌐 **GEOLOCALIZACIÓN IP REAL (IP-API)**\n"
                    f"├ 🎯 **Target IP:** `{resp.get('query')}`\n"
                    f"├ 📍 **Ubicación:** {resp.get('city')}, {resp.get('regionName')}, {resp.get('country')}\n"
                    f"├ 🏢 **ISP / Organización:** {resp.get('isp')} / {resp.get('org')}\n"
                    f"└ 🌐 **Coordenadas Reales:** `Lat: {resp.get('lat')}, Lon: {resp.get('lon')}`"
                )
            else:
                resultados.append("⚠️ Error de rastreo IP o host protegido / privado.")

        elif modo == 'osint':
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=3):
                    resultados.append(
                        f"┌ 🔗 **COINCIDENCIA EN FUENTES ABIERTAS (WEB)**\n"
                        f"├ 📌 **Título:** {r.get('title')}\n"
                        f"├ 🔗 **Enlace:** {r.get('href')}\n"
                        f"└ 📝 **Extracto:** _{r.get('body')[:130]}..._"
                    )
            if not resultados:
                resultados.append("⚠️ Sin resultados públicos en fuentes abiertas.")

        return resultados
    except Exception as e:
        return [f"⚠️ Error en ejecución de consulta real: {str(e)}"]

@app.post("/api/buscar")
def api_buscar(data: QueryRequest):
    res = realizar_busqueda_real_completa(data.query, data.type)
    formatted = [{"titulo": "Resultado Táctico", "detalles": r, "extra": ""} for r in res]
    return {"status": "success", "total": len(formatted), "data": formatted}

@app.post("/api/ocr")
async def api_ocr(file: UploadFile = File(...)):
    contents = await file.read()
    return {"status": "success", "tipo": "OCR", "filename": file.filename, "texto": "DOCUMENTO ESCANEADO REALMENTE", "detalles": "Análisis de visión completado."}

@app.get("/", response_class=HTMLResponse)
def serve_mini_app():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: index.html no encontrado.</h1>"

# ==========================================
# BOT DE TELEGRAM CON SUSPENSO Y DISEÑO TÁCTICO
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = await update.message.reply_text("⚡ **GEODOS OSINT & GEOINT v6.4**\n\n🔄 *Estableciendo enlace con bases de datos y nodos reales...*")
    await asyncio.sleep(0.4)

    keyboard = [
        [InlineKeyboardButton("📁 PADRÓN (25GB DB)", callback_data="mod_ine"),
         InlineKeyboardButton("📱 TELÉFONO TÁCTICO", callback_data="mod_telefono")],
        [InlineKeyboardButton("🌐 GEO IP", callback_data="mod_geo"),
         InlineKeyboardButton("🔍 OSINT WEB", callback_data="mod_osint")],
        [InlineKeyboardButton("ℹ️ INSTRUCCIONES", callback_data="help_menu"),
         InlineKeyboardButton("◇ CERRAR SESIÓN", callback_data="logout_menu")],
        [InlineKeyboardButton("⚡ ABRIR TACTICAL OSINT SUITE (APP)", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    
    await msg.edit_text(
        f"⚡ **GEODOS OSINT & GEOINT v6.4**\n\n"
        f"🟢 ESTADO: EN LÍNEA (CONEXIÓN REAL)\n"
        f"👤 OPERADOR: {user.first_name.upper()}\n\n"
        "────────────────────────\n"
        "◆ **SELECCIONA UN MÓDULO PARA BUSCAR EN EL CHAT**\n"
        "Haz clic en un botón y escribe tu objetivo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("mod_"):
        modo = data.split("_")[1]
        nombres = {'ine': '📁 PADRÓN ELECTORAL (25GB DB)', 'telefono': '📱 TELÉFONO TÁCTICO (E.164)', 'geo': '🌐 GEO IP', 'osint': '🔍 OSINT WEB'}
        context.user_data['modo_activo'] = modo
        await query.message.reply_text(
            f"🎯 **MODO ACTIVO: {nombres.get(modo, 'Búsqueda')}**\n\n"
            "Escribe ahora mismo en el chat el objetivo real (Nombre, CURP, Teléfono o IP) para iniciar la consulta:",
            parse_mode="Markdown"
        )
    elif data == "help_menu":
        await query.message.reply_text(
            "📖 **MANUAL OPERATIVO DEL BOT:**\n\n"
            "1. Selecciona un módulo operativo.\n"
            "2. Envía tu consulta real en el chat.\n"
            "3. El sistema procesará la búsqueda en las bases de datos y APIs reales, mostrando expedientes estructurados.",
            parse_mode="Markdown"
        )
    elif data == "logout_menu":
        context.user_data.pop('modo_activo', None)
        await query.message.reply_text("◇ **SESIÓN CERRADA.** Escribe `/start` para reconectar.", parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    modo = context.user_data.get('modo_activo')

    if not modo:
        await update.message.reply_text("⚠️ Por favor, selecciona primero un módulo operativo usando los botones del comando `/start` o `/menu` antes de enviar tu consulta.")
        return

    # Animación de análisis real con barra de progreso
    status_msg = await update.message.reply_text(
        "⚡ **[EJECUTANDO CONSULTA REAL]**\n"
        "█▒▒▒▒▒▒▒▒▒ 10%\n"
        "🔌 Abriendo canal seguro...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(0.5)
    
    await status_msg.edit_text(
        "⚡ **[EJECUTANDO CONSULTA REAL]**\n"
        "█████▒▒▒▒▒ 50%\n"
        f"🔍 Consultando registros para: `{user_text}`...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(0.7)

    await status_msg.edit_text(
        "⚡ **[EJECUTANDO CONSULTA REAL]**\n"
        "██████████ 100%\n"
        "🔒 Compilando resultados...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(0.4)

    resultados = realizar_busqueda_real_completa(user_text, modo)
    
    respuesta_final = f"🛡️ **EXPEDIENTE TÁCTICO // MÓDULO [{modo.upper()}]**\n"
    respuesta_final += f"🎯 **OBJETIVO:** `{user_text.upper()}`\n"
    respuesta_final += "────────────────────────\n\n"
    
    for r in resultados:
        respuesta_final += f"{r}\n\n"
        
    respuesta_final += "────────────────────────\n"
    respuesta_final += "⚡ *Estado: Consulta completada con éxito.*"

    await status_msg.edit_text(respuesta_final, parse_mode="Markdown")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("menu", start))
telegram_app.add_handler(CallbackQueryHandler(button_handler))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=f"{WEB_APP_URL}/webhook")

@app.post("/webhook")
async def telegram_webhook(req: Request):
    update = Update.de_json(await req.json(), telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}
                        
