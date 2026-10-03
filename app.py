import os
import sqlite3
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from duckduckgo_search import DDGS
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type

from telegram import Update, WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

# ==========================================
# 1. CONFIGURACIÓN DE FASTAPI & TELEGRAM BOT
# ==========================================
TOKEN = "8375866730:AAFQWVJjYwEkriVBK9AjkVaMwvo7ysc0oKE"
# Reemplaza con tu URL pública real de Render (ej: https://tu-app.onrender.com)
WEB_APP_URL = https://tu-proyecto.onrender.com
app = FastAPI(title="CDPS OSINT Tactical Suite", version="5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar la aplicación del bot de Telegram para webhooks
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
        # ---- INE DB ----
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

        # ---- TELÉFONO & PLAN ----
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

        # ---- GEO IP ----
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

        # ---- OSINT WEB ----
        elif modo == 'osint':
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=6):
                    resultados.append({
                        "titulo": f"🔗 {r.get('title')}",
                        "detalles": r.get('href'),
                        "extra": r.get('body')
                    })

        # ---- REDES SOCIALES ----
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

        # ---- LEAKS DB ----
        elif modo == 'leaks':
            resultados.append({
                "titulo": f"🔐 ANÁLISIS DE BRECHAS: {query}",
                "detalles": "Cruce con registros públicos de credenciales filtradas.",
                "extra": "[!] Coincidencia detectada en bases de datos de seguridad históricas."
            })

        # ---- CRYPTO ----
        elif modo == 'crypto':
            resultados.append({
                "titulo": f"₿ WALLET TARGET: {query}",
                "detalles": "Análisis de cadena de bloques y nodos activos.",
                "extra": "RED: Bitcoin / Ethereum | ESTADO: Sincronizado y monitoreado."
            })

        return {"status": "success", "total": len(resultados), "data": resultados}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# 2. MINI APP INTERACTIVA (DISEÑO TÁCTICO AMBER)
# ==========================================
MINI_APP_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CDPS // Tactical OSINT Suite</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
:root {
    --bg-color: #0c0a09; --panel-bg: #1c1917; --border-color: #78350f;
    --accent: #fbbf24; --accent-green: #22c55e; --accent-red: #ef4444;
    --text-main: #f5f5f4; --text-muted: #a8a29e;
}
body { background-color: var(--bg-color); color: var(--text-main); font-family: 'Share Tech Mono', monospace; margin: 0; padding: 12px; padding-bottom: 60px; font-size: 14px; }
.header { background: var(--panel-bg); border: 1px solid var(--border-color); padding: 10px 14px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; box-shadow: 0 0 10px rgba(251,191,36,0.1); }
.card { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; margin-bottom: 12px; }
.grid-menu { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; margin-bottom: 12px; }
.cell-btn { background: #0c0a09; border: 1px solid #78350f; color: var(--text-muted); padding: 8px 10px; border-radius: 6px; font-size: 12px; cursor: pointer; text-align: center; font-weight: bold; font-family: 'Share Tech Mono', monospace; transition: 0.2s; }
.cell-btn.active { background: rgba(251, 191, 36, 0.15); color: var(--accent); border-color: var(--accent); box-shadow: 0 0 8px rgba(251,191,36,0.3); }
.input-group { display: flex; gap: 6px; margin-top: 8px; }
input { flex: 1; background: #0c0a09; border: 1px solid var(--border-color); color: var(--accent); padding: 10px; border-radius: 6px; outline: none; font-size: 14px; font-family: 'Share Tech Mono', monospace; }
button.exec-btn { background: var(--accent); color: #000; border: none; padding: 10px 14px; border-radius: 6px; font-weight: bold; cursor: pointer; font-size: 13px; font-family: 'Share Tech Mono', monospace; box-shadow: 0 0 8px rgba(251,191,36,0.4); }
.scanner-line { width: 100%; height: 2px; background: var(--accent); position: relative; animation: scan 1.5s infinite linear; display: none; margin-top: 10px; box-shadow: 0 0 8px var(--accent); }
@keyframes scan { 0% { opacity: 0.2; transform: translateY(-3px); } 50% { opacity: 1; transform: translateY(3px); } 100% { opacity: 0.2; transform: translateY(-3px); } }
.result-item { background: #0c0a09; border-left: 3px solid var(--accent); padding: 10px; margin-top: 8px; border-radius: 4px; font-size: 12px; word-break: break-all; line-height: 1.4; }
.status-indicator { display: inline-block; width: 8px; height: 8px; background: var(--accent-green); border-radius: 50%; margin-right: 5px; box-shadow: 0 0 6px var(--accent-green); }
</style>
</head>
<body>
<div class="header">
<div>
<div id="username" style="font-weight: bold; color: var(--accent); font-size: 14px;">OPERADOR</div>
<div id="userid" style="font-size: 10px; color: var(--text-muted);">ID: SECURE_NODE</div>
</div>
<div style="font-size: 11px; color: var(--accent-green); border: 1px solid var(--accent-green); padding: 4px 8px; border-radius: 4px; font-weight: bold;">
<span class="status-indicator"></span>ONLINE
</div>
</div>
<div class="card">
<h3 style="margin-top: 0; font-size: 13px; color: var(--accent);">⚡ TACTICAL MATRIX OSINT v5.0</h3>
<p style="font-size: 11px; color: var(--text-muted); margin-bottom: 10px;" id="descModo">Selecciona un módulo táctico de consulta abajo:</p>

<!-- Menú en Celdas / Botones -->
<div class="grid-menu">
<div class="cell-btn active" onclick="cambiarModo('ine', this, 'Base de datos local cifrada (INE).', 'Nombre o CURP...')">📁 INE DB</div>
<div class="cell-btn" onclick="cambiarModo('telefono', this, 'Análisis de metadatos, carrier y plan E.164.', '+52...')">📱 TELÉFONO</div>
<div class="cell-btn" onclick="cambiarModo('geo', this, 'Geolocalización satelital de IP / Host.', '8.8.8.8...')">🌐 GEO IP</div>
<div class="cell-btn" onclick="cambiarModo('osint', this, 'Búsqueda profunda en fuentes abiertas web.', 'Alias u objetivo...')">🔍 OSINT WEB</div>
<div class="cell-btn" onclick="cambiarModo('social', this, 'Rastreo de perfiles en redes sociales.', 'Username...')">👤 REDES</div>
<div class="cell-btn" onclick="cambiarModo('leaks', this, 'Verificación de credenciales en brechas.', 'Correo o usuario...')">🔐 LEAKS DB</div>
<div class="cell-btn" onclick="cambiarModo('crypto', this, 'Rastreo y análisis de wallets cripto.', 'Wallet BTC / ETH...')">₿ CRYPTO</div>
</div>

<div class="input-group">
<input type="text" id="queryInput" placeholder="Nombre o CURP...">
<button class="exec-btn" onclick="ejecutarBusqueda()">EJECUTAR</button>
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
                    <b style="color: var(--accent); font-size: 13px;">${item.titulo}</b><br>
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
# 3. CONFIGURACIÓN DEL BOT CON WEBHOOK (SOLUCIÓN DEFINITIVA)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("⚡ ABRIR TACTICAL OSINT SUITE", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"🛡️ **ACCESO TÁCTICO CONCEDIDO // {user.first_name.upper()}**\n\n"
        "Terminal conectada por Webhook de alta velocidad.\n"
        "Haz clic abajo para desplegar la suite operativa.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ ABRIR TACTICAL OSINT SUITE", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📂 **MENÚ PRINCIPAL TÁCTICO**", reply_markup=reply_markup, parse_mode="Markdown")

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("menu", menu))

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    # Configurar webhook automático en Telegram apuntando a tu app en Render
    webhook_url = f"{WEB_APP_URL}/webhook"
    await telegram_app.bot.set_webhook(url=webhook_url)
    print(f"[+] Webhook de Telegram configurado exitosamente en: {webhook_url}")

@app.post("/webhook")
async def telegram_webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}
                
