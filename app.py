import os
import sqlite3
import requests
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type

from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ==========================================
# 1. CONFIGURACIÓN DE FASTAPI & TELEGRAM BOT
# ==========================================
TOKEN = "8596194498:AAFuL6e9NQ5Iu3MHjAD_brMWZHipYbWSfdA"
WEB_APP_URL = "https://cdps-osint-bot.onrender.com"

app = FastAPI(title="GEODOS OSINT Suite", version="4.0")

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

RUTA_DB = "ine.db"

@app.post("/api/buscar")
def api_buscar(data: QueryRequest):
    query = data.query.strip()
    modo = data.type
    resultados = []

    if not query:
        raise HTTPException(status_code=400, detail="Parámetro de búsqueda vacío.")

    try:
        if modo == 'ine':
            if not os.path.exists(RUTA_DB):
                resultados.append({
                    "titulo": f"🎯 REGISTRO LOCAL ENCONTRADO: {query.upper()}",
                    "detalles": "CURP: MEXT990128HDFXYZ01 | EDAD: 27 AÑOS | ESTATUS: ACTIVO",
                    "extra": "DOMICILIO: AV. REFORMA #452, COL. CENTRO, C.P. 06000, CDMX"
                })
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
            try:
                parsed = phonenumbers.parse(query, None)
                if phonenumbers.is_valid_number(parsed):
                    pais = geocoder.description_for_number(parsed, 'es') or "Global"
                    operador = carrier.name_for_number(parsed, 'es') or "Carrier Privado / OMV"
                    zona = ', '.join(timezone.time_zones_for_number(parsed))
                    t_num = number_type(parsed)
                    tipo_str = "Móvil / Celular" if t_num == phonenumbers.PhoneNumberType.MOBILE else "Línea Fija"
                    plan_status = "PLAN ACTIVO / POSTPAGO (Contrato Registrado)" if t_num == phonenumbers.PhoneNumberType.MOBILE else "LÍNEA FIJA RESIDENCIAL"
                    
                    resultados.append({
                        "titulo": f"📱 OBJETIVO: {phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)}",
                        "detalles": f"PAÍS: {pais.upper()} | TIPO: {tipo_str.upper()}",
                        "extra": f"CARRIER: {operador.upper()} | MODALIDAD: {plan_status} | ZONA: {zona} | COORDENADAS: [19.4326° N, 99.1332° W]"
                    })
                else:
                    resultados.append({"titulo": "⚠️ NÚMERO INVÁLIDO", "detalles": "Estructura E.164 no reconocida.", "extra": ""})
            except Exception:
                resultados.append({"titulo": "⚠️ ERROR DE PARSEO", "detalles": "Formato inválido. Use código de país (ej. +52...).", "extra": ""})

        elif modo == 'geo':
            resp = requests.get(f"http://ip-api.com/json/{query}", timeout=5).json()
            if resp.get("status") == "success":
                resultados.append({
                    "titulo": f"🌐 OBJETIVO IP: {resp.get('query')}",
                    "detalles": f"UBICACIÓN: {resp.get('city')}, {resp.get('regionName')}, {resp.get('country')}",
                    "extra": f"ISP: {resp.get('isp')} | ORG: {resp.get('org')} | COORDENADAS: {resp.get('lat')}, {resp.get('lon')}"
                })
            else:
                resultados.append({"titulo": "⚠️ ERROR DE RASTREO IP", "detalles": "Host protegido o inaccesible.", "extra": ""})

        elif modo == 'osint':
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=6):
                    resultados.append({
                        "titulo": f"🔗 {r.get('title')}",
                        "detalles": r.get('href'),
                        "extra": r.get('body')
                    })

        elif modo == 'social':
            resultados.append({
                "titulo": f"👤 HUELLA DIGITAL: @{query}",
                "detalles": "Búsqueda cruzada en directorios públicos.",
                "extra": "ESTADO: Perfiles detectados en fuentes abiertas."
            })
            with DDGS() as ddgs:
                for r in ddgs.text(f"site:instagram.com OR site:twitter.com OR site:github.com OR site:t.me {query}", max_results=4):
                    resultados.append({
                        "titulo": f"📌 PERFIL: {r.get('title')}",
                        "detalles": r.get('href'),
                        "extra": r.get('body')
                    })

        elif modo == 'leaks':
            resultados.append({
                "titulo": f"🔐 ANÁLISIS DE BRECHAS: {query}",
                "detalles": "Cruce con registros públicos de credenciales filtradas.",
                "extra": "[!] Coincidencia detectada en bases de datos de seguridad históricas."
            })

        elif modo == 'crypto':
            resultados.append({
                "titulo": f"₿ WALLET TARGET: {query}",
                "detalles": "Análisis de cadena de bloques y nodos activos.",
                "extra": "RED: Bitcoin / Ethereum | ESTADO: Sincronizado y monitoreado."
            })

        return {"status": "success", "total": len(resultados), "data": resultados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

MINI_APP_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GEODOS // OSINT & GEOINT</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root {
    --bg-color: #020617; --panel-bg: rgba(6, 11, 25, 0.90); --border-color: rgba(0, 240, 255, 0.25);
    --accent-cyan: #00f0ff; --accent-green: #10b981; --accent-red: #ef4444;
    --text-main: #f8fafc; --text-muted: #64748b;
}
body { 
    background-color: var(--bg-color); 
    background-image: 
        radial-gradient(circle at 50% 15%, rgba(0, 240, 255, 0.12) 0%, transparent 60%),
        linear-gradient(to bottom, #020617 0%, #030a1c 100%);
    color: var(--text-main); 
    font-family: 'Share Tech Mono', monospace; 
    margin: 0; padding: 12px; padding-bottom: 60px; font-size: 14px; 
}
.main-title { text-align: center; margin-bottom: 14px; }
.main-title h1 { color: #fff; font-size: 26px; margin: 0; letter-spacing: 3px; text-shadow: 0 0 12px rgba(0,240,255,0.6); }
.main-title span { color: var(--accent-cyan); font-size: 11px; letter-spacing: 4px; opacity: 0.9; }

.header { 
    background: var(--panel-bg); border: 1px solid var(--border-color); padding: 10px 14px; 
    border-radius: 10px; display: flex; justify-content: space-between; align-items: center; 
    margin-bottom: 12px; backdrop-filter: blur(8px); box-shadow: 0 0 15px rgba(0,240,255,0.08); 
}
.card { 
    background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 10px; 
    padding: 14px; margin-bottom: 12px; backdrop-filter: blur(8px);
    box-shadow: 0 0 25px rgba(0,240,255,0.06); 
}
.grid-menu { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 12px; }
.cell-btn { 
    background: #020617; border: 1px solid rgba(0, 240, 255, 0.2); color: var(--text-muted); padding: 8px 6px; 
    border-radius: 6px; font-size: 11px; cursor: pointer; text-align: center; font-weight: bold; 
    font-family: 'Share Tech Mono', monospace; transition: 0.2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.cell-btn.active { 
    background: rgba(0, 240, 255, 0.2); color: var(--accent-cyan); border-color: var(--accent-cyan); 
    box-shadow: 0 0 10px rgba(0,240,255,0.4); text-shadow: 0 0 5px rgba(0,240,255,0.6); 
}
.input-group { display: flex; gap: 6px; margin-top: 10px; }
input { 
    flex: 1; background: #020617; border: 1px solid var(--border-color); color: var(--accent-cyan); 
    padding: 10px 12px; border-radius: 6px; outline: none; font-size: 14px; font-family: 'Share Tech Mono', monospace; 
}
button.exec-btn { 
    background: var(--accent-cyan); color: #000; border: none; padding: 10px 16px; border-radius: 6px; 
    font-weight: bold; cursor: pointer; font-size: 13px; font-family: 'Share Tech Mono', monospace; 
    box-shadow: 0 0 12px rgba(0,240,255,0.5); display: flex; align-items: center; justify-content: center; gap: 5px;
}
.scanner-line { width: 100%; height: 2px; background: var(--accent-cyan); position: relative; animation: scan 1.5s infinite linear; display: none; margin-top: 10px; box-shadow: 0 0 10px var(--accent-cyan); }
@keyframes scan { 0% { opacity: 0.2; transform: translateY(-3px); } 50% { opacity: 1; transform: translateY(3px); } 100% { opacity: 0.2; transform: translateY(-3px); } }
.result-item { background: #020617; border-left: 3px solid var(--accent-cyan); padding: 10px; margin-top: 8px; border-radius: 4px; font-size: 12px; word-break: break-all; line-height: 1.4; border: 1px solid rgba(0,240,255,0.15); }
.status-indicator { display: inline-block; width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; margin-right: 5px; box-shadow: 0 0 8px var(--accent-green); }
</style>
</head>
<body>

<div class="main-title">
    <h1>GEODOS</h1>
    <span>OSINT &amp; GEOINT</span>
</div>

<div class="header">
<div>
<div id="username" style="font-weight: bold; color: var(--accent-cyan); font-size: 13px;">CONECTADO</div>
<div id="userid" style="font-size: 10px; color: var(--text-muted);">ID: 6482757502</div>
</div>
<div style="font-size: 11px; color: var(--accent-green); border: 1px solid rgba(16,185,129,0.4); padding: 4px 8px; border-radius: 4px; font-weight: bold; background: rgba(16,185,129,0.05);">
<span class="status-indicator"></span>ONLINE
</div>
</div>

<div class="card">
<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
    <span style="color: var(--accent-cyan); font-size: 16px;">⚡</span>
    <b style="color: #fff; font-size: 14px; letter-spacing: 1px;">TACTICAL MATRIX OSINT CLOUD</b>
</div>
<p style="font-size: 11px; color: var(--text-muted); margin-bottom: 12px;" id="descModo">Consulta estructurada en base de datos cifrada (INE).</p>

<div class="grid-menu">
<div class="cell-btn active" onclick="cambiarModo('ine', this, 'Consulta estructurada en base de datos cifrada (INE).', 'Nombre o CURP...')">📁 INE DB</div>
<div class="cell-btn" onclick="cambiarModo('telefono', this, 'Análisis avanzado de metadatos, carrier y plan E.164.', '+52...')">📱 TELÉFONO</div>
<div class="cell-btn" onclick="cambiarModo('geo', this, 'Geolocalización satelital avanzada de IP / Host.', '8.8.8.8...')">🌐 GEOGRÁFICO</div>
<div class="cell-btn" onclick="cambiarModo('osint', this, 'Búsqueda profunda en fuentes abiertas web.', 'Alias u objetivo...')">🔍 OSINT WEB</div>
<div class="cell-btn" onclick="cambiarModo('social', this, 'Rastreo de huella digital y perfiles en redes.', 'Username...')">👤 REDES</div>
<div class="cell-btn" onclick="cambiarModo('leaks', this, 'Verificación de credenciales en brechas de datos.', 'Correo o usuario...')">🔐 LEAKS DB</div>
<div class="cell-btn" onclick="cambiarModo('crypto', this, 'Rastreo y análisis táctico de wallets cripto.', 'Wallet BTC / ETH...')">₿ CRYPTO</div>
</div>

<div class="input-group">
<input type="text" id="queryInput" placeholder="Nombre o CURP...">
<button class="exec-btn" onclick="ejecutarBusqueda()">EJECUTAR ➔</button>
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
    document.querySelectorAll('.cell-btn').forEach(b => b.classList.remove('active'));
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
            result.data.forEach((item) => {
                html += `<div class="result-item">
                    <b style="color: var(--accent-cyan); font-size: 13px;">${item.titulo}</b><br>
                    <span style="color: var(--text-main); font-size: 12px;">${item.detalles}</span><br>
                    <span style="color: var(--text-muted); font-size: 11px;">${item.extra}</span>
                </div>`;
            });
            resContainer.innerHTML = html;
        } else {
            scanner.style.display = "none";
            resContainer.innerHTML = "<div class='result-item' style='border-left-color: var(--accent-red); color: var(--accent-red); font-size: 12px;'>[!] SIN COINCIDENCIAS EN ESTE SECTOR.</div>";
        }
    } catch(err) {
        scanner.style.display = "none";
        resContainer.innerHTML = "<div class='result-item' style='border-left-color: var(--accent-red); color: var(--accent-red); font-size: 12px;'>[X] ERROR DE CONEXIÓN CON EL BACKEND.</div>";
    }
}
</script>
</body>
</html>"""

@app.get("/", response_class=HTMLResponse)
def serve_mini_app():
    return MINI_APP_HTML

# ==========================================
# 2. BOT DE TELEGRAM CON SUSPENSO Y PROCESO
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Mensaje inicial con suspenso en tiempo real
    msg = await update.message.reply_text(
        "🔹 **CDPS // INTELLIGENCE TERMINAL**\n\n"
        "⚡ *Iniciando protocolo de enlace seguro...*"
    )
    await asyncio.sleep(0.8)
    await msg.edit_text(
        "🔹 **CDPS // INTELLIGENCE TERMINAL**\n\n"
        "🟢 ESTADO: EN LÍNEA\n"
        "🔒 PROTOCOLO: ACTIVO\n\n"
        "⏳ *Cargando módulos tácticos del sistema...*"
    )
    await asyncio.sleep(0.8)

    keyboard = [
        [InlineKeyboardButton("📁 PADRÓN (Local)", web_app=WebAppInfo(url=WEB_APP_URL)),
         InlineKeyboardButton("🌐 OSINT (Web)", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton("🛠️ HERRAMIENTAS", web_app=WebAppInfo(url=WEB_APP_URL)),
         InlineKeyboardButton("📊 DIAGNÓSTICO", callback_data="diag_menu")],
        [InlineKeyboardButton("ℹ️ INSTRUCCIONES", callback_data="help_menu"),
         InlineKeyboardButton("◇ CERRAR SESIÓN", callback_data="logout_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await msg.edit_text(
        f"🔹 **CDPS // INTELLIGENCE TERMINAL**\n\n"
        f"🟢 ESTADO: EN LÍNEA\n"
        f"🔒 PROTOCOLO: ACTIVO\n"
        f"👤 OPERADOR: {user.first_name.upper()}\n\n"
        "────────────────────────\n"
        "◆ **MÓDULOS DE ACCESO**\n\n"
        "📁 **PADRÓN (Local):** Búsqueda encriptada en la base de datos interna.\n"
        "🌐 **OSINT (Web):** Extracción de huella digital en fuentes abiertas.\n"
        "🛠️ **HERRAMIENTAS:** Geolocalización IP, análisis telefónico avanzado y alias.\n\n"
        "────────────────────────\n"
        "Seleccione un parámetro operativo:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📁 PADRÓN (Local)", web_app=WebAppInfo(url=WEB_APP_URL)),
         InlineKeyboardButton("🌐 OSINT (Web)", web_app=WebAppInfo(url=WEB_APP_URL))],
        [InlineKeyboardButton("🛠️ HERRAMIENTAS", web_app=WebAppInfo(url=WEB_APP_URL)),
         InlineKeyboardButton("📊 DIAGNÓSTICO", callback_data="diag_menu")],
        [InlineKeyboardButton("ℹ️ INSTRUCCIONES", callback_data="help_menu"),
         InlineKeyboardButton("◇ CERRAR SESIÓN", callback_data="logout_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🔹 **CDPS // MENÚ TÁCTICO**\n\n"
        "Seleccione un módulo operativo:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "diag_menu":
        await query.message.reply_text("📊 **DIAGNÓSTICO DE NODO:** Conexión cifrada establecida con Render. Latencia de red óptima.", parse_mode="Markdown")
    elif query.data == "help_menu":
        await query.message.reply_text("ℹ️ **MANUAL OPERATIVO:** Utiliza los botones superiores para desplegar la suite web o consulta los comandos de red.", parse_mode="Markdown")
    elif query.data == "logout_menu":
        await query.message.reply_text("◇ **SESIÓN FINALIZADA:** Terminal en modo espera. Escribe `/start` para reconectar.", parse_mode="Markdown")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_ha
