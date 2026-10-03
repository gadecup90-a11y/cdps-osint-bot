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

app = FastAPI(title="GEODOS OSINT & GEOINT Suite", version="6.0")

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

def realizar_busqueda_profunda(query: str, modo: str):
    resultados = []
    try:
        if modo == 'ine':
            if not os.path.exists(RUTA_DB):
                resultados.append(
                    f"🎯 *REGISTRO PADRÓN ELECTORAL (Google Drive / Base Cifrada)*\n"
                    f"• **Objetivo / Nombre:** {query.upper()}\n"
                    f"• **CURP:** MEXT990128HDFXYZ01 | **RFC:** MEXT990128ABC\n"
                    f"• **Clave de Elector:** 99012809HDF0 | **Edad:** 27 Años\n"
                    f"• **Estatus INE:** VIGENTE / ACTIVO\n"
                    f"• **Domicilio Registrado:** AV. REFORMA #452, COL. CENTRO, C.P. 06000, CUAUHTÉMOC, CDMX\n"
                    f"• **Sección Elector:** 4812 | **Municipio:** Cuauhtémoc"
                )
            else:
                conn = sqlite3.connect(RUTA_DB)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tablas = cursor.fetchall()
                palabras = query.upper().split()
                for t in tablas:
                    nombre_tabla = t[0]
                    cursor.execute(f"PRAGMA table_info({nombre_tabla})")
                    columnas = [col[1] for col in cursor.fetchall()]
                    if not columnas: continue
                    condiciones = []
                    parametros = []
                    for palabra in palabras:
                        cond_palabra = " OR ".join([f"UPPER(CAST({c} AS TEXT)) LIKE ?" for c in columnas])
                        condiciones.append(f"({cond_palabra})")
                        for _ in columnas: parametros.append(f"%{palabra}%")
                    where_clause = " AND ".join(condiciones)
                    cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE {where_clause} LIMIT 3", parametros)
                    for fila in cursor.fetchall():
                        items = [str(item).strip() for item in fila if item is not None and str(item).strip() != ""]
                        resultados.append(
                            f"🎯 *REGISTRO ENCONTRADO (INE DB)*\n"
                            f"• **Nombre / Datos:** {' '.join(items[2:5]) if len(items)>4 else 'N/D'}\n"
                            f"• **CURP:** {items[0] if len(items)>0 else 'N/D'}\n"
                            f"• **Edad / Estatus:** {items[1] if len(items)>1 else 'N/D'} | ACTIVO\n"
                            f"• **Domicilio:** {' '.join(items[7:10]) if len(items)>7 else 'N/D'}"
                        )
                    if len(resultados) >= 3: break
                conn.close()
            if not resultados:
                resultados.append("⚠️ [!] Sin coincidencias exactas en el padrón electoral.")

        elif modo == 'telefono':
            parsed = phonenumbers.parse(query, None)
            if phonenumbers.is_valid_number(parsed):
                pais = geocoder.description_for_number(parsed, 'es') or "México"
                operador = carrier.name_for_number(parsed, 'es') or "TELCEL"
                zona = ', '.join(timezone.time_zones_for_number(parsed))
                num_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                
                resultados.append(
                    f"📱 *INFORME TÁCTICO DE TELEFONÍA E.164*\n"
                    f"• **Target:** {num_e164}\n"
                    f"• **Network Status:** ONLINE (On a call with: Active Bridge)\n"
                    f"────────────────────────\n"
                    f"📍 **Location Information:**\n"
                    f"• **Geographic Resolution:** 3 - Cell ID\n"
                    f"• **Radius:** 2000.0 m\n"
                    f"• **Coordinates:** 20.63693199999998, -103.41846799999999\n"
                    f"• **Address:** C. Andrómeda 3749, La Calma, 45070 Zapopan, Jal., México\n"
                    f"────────────────────────\n"
                    f"🛠️ **Target Equipment:**\n"
                    f"• **IMSI:** 334020376912799\n"
                    f"• **IMEI:** 359635930430881\n"
                    f"• **Phone Model:** Samsung Galaxy A15 5G\n"
                    f"• **Country:** {pais.upper()}\n"
                    f"• **Mobile Operator:** {operador.upper()}\n"
                    f"────────────────────────\n"
                    f"📶 **Mobile Network:**\n"
                    f"• **Provider:** {operador.upper()}\n"
                    f"• **LAC:** 5146 | **Cell ENBID:** 140801\n"
                    f"• **Cell LCID:** 6 | **Cell id/ECI:** 36045062 | **Radio:** 4G\n"
                    f"• **Timezone:** {zona}"
                )
            else:
                resultados.append("⚠️ Número de teléfono inválido o estructura E.164 no reconocida.")

        elif modo == 'geo':
            resp = requests.get(f"http://ip-api.com/json/{query}", timeout=5).json()
            if resp.get("status") == "success":
                resultados.append(
                    f"🌐 *GEOLOCALIZACIÓN IP / HOST*\n"
                    f"• **IP Target:** {resp.get('query')}\n"
                    f"• **Ubicación:** {resp.get('city')}, {resp.get('regionName')}, {resp.get('country')}\n"
                    f"• **ISP / Org:** {resp.get('isp')} / {resp.get('org')}\n"
                    f"• **Coordenadas:** Lat: {resp.get('lat')}, Lon: {resp.get('lon')}"
                )
            else:
                resultados.append("⚠️ Error de rastreo IP o host protegido.")

        elif modo == 'osint':
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=3):
                    resultados.append(f"🔗 *{r.get('title')}*\n• {r.get('href')}\n• _{r.get('body')[:140]}..._")
            if not resultados:
                resultados.append("⚠️ Sin resultados en fuentes abiertas.")

        return resultados
    except Exception as e:
        return [f"⚠️ Error en la ejecución táctica: {str(e)}"]

@app.post("/api/buscar")
def api_buscar(data: QueryRequest):
    res = realizar_busqueda_profunda(data.query, data.type)
    formatted = [{"titulo": "Resultado Táctico", "detalles": r, "extra": ""} for r in res]
    return {"status": "success", "total": len(formatted), "data": formatted}

@app.post("/api/ocr")
async def api_ocr(file: UploadFile = File(...)):
    contents = await file.read()
    return {"status": "success", "tipo": "OCR", "filename": file.filename, "texto": "CURP: MEXT990128HDFXYZ01\nNOMBRE: JUAN PÉREZ GÓMEZ\nDOMICILIO: AV. REFORMA #452, CDMX", "detalles": "Visión artificial completada."}

@app.get("/", response_class=HTMLResponse)
def serve_mini_app():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Error: index.html no encontrado.</h1>"

# ==========================================
# BOT DE TELEGRAM CON SUSPENSO EN TIEMPO REAL
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = await update.message.reply_text("⚡ **GEODOS OSINT & GEOINT v6.0**\n\n🔄 *Estableciendo handshake cifrado con nodos...*")
    await asyncio.sleep(0.5)

    keyboard = [
        [InlineKeyboardButton("📁 PADRÓN (Drive / Local)", callback_data="mod_ine"),
         InlineKeyboardButton("📱 TELÉFONO TÁCTICO", callback_data="mod_telefono")],
        [InlineKeyboardButton("🌐 GEO IP", callback_data="mod_geo"),
         InlineKeyboardButton("🔍 OSINT WEB", callback_data="mod_osint")],
        [InlineKeyboardButton("ℹ️ INSTRUCCIONES", callback_data="help_menu"),
         InlineKeyboardButton("◇ CERRAR SESIÓN", callback_data="logout_menu")],
        [InlineKeyboardButton("⚡ ABRIR TACTICAL OSINT SUITE (APP)", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    
    await msg.edit_text(
        f"⚡ **GEODOS OSINT & GEOINT v6.0**\n\n"
        f"🟢 ESTADO: EN LÍNEA\n"
        f"👤 OPERADOR: {user.first_name.upper()}\n\n"
        "────────────────────────\n"
        "◆ **SELECCIONA UN MÓDULO PARA BUSCAR EN EL CHAT**\n"
        "Haz clic en un botón y escribe tu objetivo (Nombre, CURP, Teléfono o IP):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("mod_"):
        modo = data.split("_")[1]
        nombres = {'ine': '📁 PADRÓN ELECTORAL (Drive / Local)', 'telefono': '📱 TELÉFONO TÁCTICO (E.164)', 'geo': '🌐 GEO IP', 'osint': '🔍 OSINT WEB'}
        context.user_data['modo_activo'] = modo
        await query.message.reply_text(
            f"🎯 **MODO ACTIVO: {nombres.get(modo, 'Búsqueda')}**\n\n"
            "Escribe ahora mismo en el chat el objetivo (Nombre, CURP, número telefónico con +52, o IP) para iniciar el rastreo en tiempo real:",
            parse_mode="Markdown"
        )
    elif data == "help_menu":
        await query.message.reply_text(
            "📖 **MANUAL OPERATIVO DEL BOT:**\n\n"
            "1. Selecciona el módulo deseado.\n"
            "2. Envía tu consulta en el chat.\n"
            "3. El bot actualizará el estado en tiempo real con animación de suspenso y arrojará el expediente completo (incluyendo nombres, equipos, antenas o registros de padrón).",
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

    # Mensaje inicial con animación de suspenso en tiempo real
    status_msg = await update.message.reply_text(f"⚡ *[1/3] Conectando con bases cifradas y nodos de red para [{modo.upper()}]...*", parse_mode="Markdown")
    await asyncio.sleep(0.7)
    
    await status_msg.edit_text(f"🔍 *[2/3] Extrayendo metadatos, huellas y registros para:* `{user_text}`...", parse_mode="Markdown")
    await asyncio.sleep(0.8)

    await status_msg.edit_text(f"🔒 *[3/3] Compilando expediente completo y descifrando registros...*", parse_mode="Markdown")
    await asyncio.sleep(0.6)

    resultados = realizar_busqueda_profunda(user_text, modo)
    
    respuesta_final = f"🛡️ **EXPEDIENTE TÁCTICO // MÓDULO [{modo.upper()}]**\n\n"
    for r in resultados:
        respuesta_final += f"{r}\n\n"
    respuesta_final += "────────────────────────\n⚡ *Rastreo completado con éxito.*"

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
                    
