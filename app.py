import os
import sqlite3
import requests
import asyncio
import threading
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
import phonenumbers
from phonenumbers import geocoder, carrier, timezone

from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ==========================================
# 1. CONFIGURACIÓN DE FASTAPI
# ==========================================
app = FastAPI(title="CDPS OSINT Cloud Suite", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    user_id: int
    query: str
    type: str

RUTA_DB = "ine.db"

@app.post("/api/buscar")
def api_buscar(data: QueryRequest):
    query = data.query.strip()
    modo = data.type
    resultados = []

    if not query:
        raise HTTPException(status_code=400, detail="Parámetro vacío.")

    try:
        if modo == 'ine':
            if not os.path.exists(RUTA_DB):
                raise HTTPException(status_code=500, detail="Base de datos local no encontrada en el servidor.")
            
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
                cursor.execute(f"SELECT * FROM {nombre_tabla} WHERE {where_clause} LIMIT 6", parametros)
                
                for fila in cursor.fetchall():
                    items = [str(item).strip() for item in fila if item is not None and str(item).strip() != ""]
                    resultados.append({
                        "titulo": f"🎯 {items[2] if len(items)>2 else ''} {items[3] if len(items)>3 else ''} {items[4] if len(items)>4 else ''}",
                        "detalles": f"CURP: {items[0] if len(items)>0 else 'N/D'} | EDAD: {items[1] if len(items)>1 else 'N/D'}",
                        "extra": f"DOMICILIO: {' '.join(items[7:10]) if len(items)>7 else 'N/D'}"
                    })
                if len(resultados) >= 6: break
            conn.close()

        elif modo == 'telefono':
            parsed = phonenumbers.parse(query, None)
            if phonenumbers.is_valid_number(parsed):
                resultados.append({
                    "titulo": f"📱 {phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)}",
                    "detalles": f"PAÍS: {geocoder.description_for_number(parsed, 'es')} | CARRIER: {carrier.name_for_number(parsed, 'es')}",
                    "extra": f"ZONA: {', '.join(timezone.time_zones_for_number(parsed))} | STATUS: VÁLIDO"
                })
            else:
                resultados.append({"titulo": "⚠️ NÚMERO INVÁLIDO", "detalles": "Estructura E.164 no reconocida.", "extra": ""})

        elif modo == 'geo':
            resp = requests.get(f"http://ip-api.com/json/{query}", timeout=5).json()
            if resp.get("status") == "success":
                resultados.append({
                    "titulo": f"🌐 OBJETIVO IP: {resp.get('query')}",
                    "detalles": f"UBICACIÓN: {resp.get('city')}, {resp.get('regionName')}, {resp.get('country')}",
                    "extra": f"ISP: {resp.get('isp')} | COORDENADAS: {resp.get('lat')}, {resp.get('lon')}"
                })
            else:
                resultados.append({"titulo": "⚠️ ERROR DE RASTREO IP", "detalles": "Host no encontrado o inaccesible.", "extra": ""})

        elif modo == 'osint':
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=5):
                    resultados.append({
                        "titulo": f"🔗 {r.get('title')}",
                        "detalles": r.get('href'),
                        "extra": r.get('body')
                    })

        return {"status": "success", "total": len(resultados), "data": resultados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

MINI_APP_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CDPS // Tactical OSINT Cloud</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root {
    --bg-color: #030712; --panel-bg: #0b1329; --border-color: #1e3a8a;
    --accent-cyan: #00f0ff; --accent-green: #10b981; --accent-red: #ef4444;
    --text-main: #e2e8f0; --text-muted: #64748b;
}
body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Share Tech Mono', monospace; margin: 0; padding: 12px; padding-bottom: 60px; }
.header { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 12px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.card { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.tabs { display: flex; gap: 4px; margin-bottom: 10px; overflow-x: auto; padding-bottom: 4px; }
.tab { background: #030712; border: 1px solid #1e3a8a; color: var(--text-muted); padding: 6px 10px; border-radius: 4px; font-size: 11px; cursor: pointer; white-space: nowrap; }
.tab.active { background: rgba(0, 240, 255, 0.15); color: var(--accent-cyan); border-color: var(--accent-cyan); }
.input-group { display: flex; gap: 6px; margin-top: 8px; }
input { flex: 1; background: #030712; border: 1px solid var(--border-color); color: var(--accent-cyan); padding: 10px; border-radius: 6px; outline: none; font-size: 13px; font-family: 'Share Tech Mono', monospace; }
button { background: var(--accent-cyan); color: #000; border: none; padding: 10px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 12px; font-family: 'Share Tech Mono', monospace; }
.scanner-line { width: 100%; height: 2px; background: var(--accent-cyan); position: relative; animation: scan 1.5s infinite linear; display: none; margin-top: 10px; }
@keyframes scan { 0% { opacity: 0.2; transform: translateY(-3px); } 50% { opacity: 1; transform: translateY(3px); } 100% { opacity: 0.2; transform: translateY(-3px); } }
.result-item { background: #030712; border-left: 3px solid var(--accent-cyan); padding: 10px; margin-top: 8px; border-radius: 4px; font-size: 12px; word-break: break-all; }
.status-indicator { display: inline-block; width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; margin-right: 5px; }
</style>
</head>
<body>
<div class="header">
<div>
<div id="username" style="font-weight: bold; color: var(--accent-cyan);">OPERADOR</div>
<div id="userid" style="font-size: 10px; color: var(--text-muted);">ID: CLOUD_NODE</div>
</div>
<div style="font-size: 11px; color: var(--accent-green); border: 1px solid var(--accent-green); padding: 4px 8px; border-radius: 4px;">
<span class="status-indicator"></span>ONLINE
</div>
</div>
<div class="card">
<h3 style="margin-top: 0; font-size: 14px; color: var(--accent-cyan);">⚡ TACTICAL MATRIX OSINT CLOUD</h3>
<p style="font-size: 11px; color: var(--text-muted);" id="descModo">Consulta estructurada en base de datos local cifrada (INE).</p>
<div class="tabs">
<div class="tab active" onclick="cambiarModo('ine', this, 'Consulta estructurada en base de datos local cifrada (INE).', 'Nombre o CURP...')">📁 INE DB</div>
<div class="tab" onclick="cambiarModo('telefono', this, 'Análisis de metadatos y portabilidad telefónica E.164.', '+52...')">📱 TELÉFONO</div>
<div class="tab" onclick="cambiarModo('geo', this, 'Geolocalización satelital y tracking de IP / Host.', '8.8.8.8...')">🌐 GEO IP</div>
<div class="tab" onclick="cambiarModo('osint', this, 'Búsqueda de inteligencia en fuentes abiertas web.', 'Alias o objetivo...')">🔍 OSINT WEB</div>
</div>
<div class="input-group">
<input type="text" id="queryInput" placeholder="Nombre o CURP...">
<button onclick="ejecutarBusqueda()">EJECUTAR</button>
</div>
<div id="scanner" class="scanner-line"></div>
<div id="results" style="margin-top: 10px;"></div>
</div>
<script>
let modoActual = 'ine';
let tg = window.Telegram.WebApp;
tg.expand();
if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    document.getElementById('username').innerText = tg.initDataUnsafe.user.first_name.toUpperCase();
    document.getElementById('userid').innerText = "ID: " + tg.initDataUnsafe.user.id;
}
function cambiarModo(modo, el, desc, placeholder) {
    modoActual = modo;
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    el.classList.add('active');
    document.getElementById('descModo').innerText = desc;
    document.getElementById('queryInput').placeholder = placeholder;
    document.getElementById('results').innerHTML = "";
}
async function ejecutarBusqueda() {
    let query = document.getElementById('queryInput').value;
    let resContainer = document.getElementById('results');
    let scanner = document.getElementById('scanner');
    if(!query) return;
    resContainer.innerHTML = "";
    scanner.style.display = "block";
    try {
        let response = await fetch('/api/buscar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: 6482757502, query: query, type: modoActual })
        });
        let result = await response.json();
        scanner.style.display = "none";
        if(result.status === 'success' && result.data.length > 0) {
            let html = "";
            result.data.forEach((item, index) => {
                html += `<div class="result-item">
                    <b style="color: var(--accent-cyan);">${item.titulo}</b><br>
                    <span style="color: var(--text-main);">${item.detalles}</span><br>
                    <span style="color: var(--text-muted); font-size: 10px;">${item.extra}</span>
                </div>`;
            });
            resContainer.innerHTML = html;
        } else {
            scanner.style.display = "none";
            resContainer.innerHTML = "<div class='result-item' style='border-left-color: var(--accent-red); color: var(--accent-red);'>[!] SIN COINCIDENCIAS EN ESTE SECTOR DE LA RED.</div>";
        }
    } catch(err) {
        scanner.style.display = "none";
        resContainer.innerHTML = "<div class='result-item' style='border-left-color: var(--accent-red); color: var(--accent-red);'>[X] ERROR CRÍTICO DE CONEXIÓN CON EL BACKEND.</div>";
    }
}
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_mini_app():
    return MINI_APP_HTML


# ==========================================
# 2. CONFIGURACIÓN DEL BOT DE TELEGRAM
# ==========================================
TOKEN = "8375866730:AAFQWVJjYwEkriVBK9AjkVaMwvo7ysc0oKE"
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://tu-proyecto.onrender.com")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
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

def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    bot_app = ApplicationBuilder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", start))
    
    print("[+] Bot de Telegram iniciado en segundo plano...")
    bot_app.run_polling()

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=run_telegram_bot, daemon=True)
    t.start()
                
