<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>OSINT CDPS - TACTICAL SUITE</title>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <style>
        body { 
            background: linear-gradient(rgba(3, 7, 18, 0.92), rgba(3, 7, 18, 0.96)), url('https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=1000&auto=format&fit=crop') no-repeat center center fixed;
            background-size: cover;
            color: #e2e8f0; 
            font-family: ui-monospace, monospace; 
        }
        .panel-tactico { 
            border: 1px solid rgba(34, 211, 238, 0.25); 
            background: rgba(5, 10, 20, 0.90); 
            backdrop-filter: blur(8px);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.7); 
        }
        .btn-comando { 
            border: 1px solid rgba(8, 145, 178, 0.4); 
            background: rgba(10, 15, 25, 0.8); 
            color: #94a3b8; 
            transition: all 0.2s; 
        }
        .btn-comando:hover, .btn-comando.active { 
            background: #0891b2; 
            color: #ffffff; 
            border-color: #22d3ee;
            box-shadow: 0 0 12px rgba(34, 211, 238, 0.4); 
            font-weight: bold; 
        }
    </style>
</head>
<body class="p-4 max-w-xl mx-auto pb-20">

    <!-- ENCABEZADO REALISTA -->
    <div class="panel-tactico p-4 mb-4 rounded-lg flex justify-between items-center border-l-4 border-cyan-400">
        <div>
            <h1 class="text-base font-extrabold tracking-wider text-white">OSINT <span class="text-cyan-400">CDPS</span></h1>
            <p class="text-[11px] text-gray-400 mt-0.5">OPERADOR: <span class="text-gray-200 font-semibold">CERVANDO</span> | ID: <span class="text-cyan-400">6482757502</span></p>
        </div>
        <div class="text-right">
            <span class="inline-block w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span class="text-[11px] text-emerald-400 font-semibold ml-1">SECURE NODE</span>
        </div>
    </div>

    <!-- PANEL DE HISTORIAL (OCULTO) -->
    <div id="panelHistorial" class="panel-tactico p-3 mb-4 rounded-lg hidden">
        <h3 class="text-xs font-bold text-cyan-400 mb-2 border-b border-gray-800 pb-1 flex justify-between">
            <span>◇ HISTORIAL DE CONSULTAS</span>
            <span class="text-[10px] text-gray-400">REGISTRO LOCAL</span>
        </h3>
        <div id="listaHistorial" class="text-xs space-y-1 max-h-40 overflow-y-auto text-gray-300 pr-1">
            <p class="text-gray-500 text-center py-2">Sin consultas registradas en esta sesión.</p>
        </div>
    </div>

    <!-- SELECTORES DE MÓDULOS / CELDAS -->
    <div class="grid grid-cols-3 gap-2 mb-3">
        <button onclick="setModo('telcel', this)" class="btn-comando active p-2.5 text-xs rounded">📱 Telcel / Celda</button>
        <button onclick="setModo('ine', this)" class="btn-comando p-2.5 text-xs rounded">📁 Padrón (24GB)</button>
        <button onclick="setModo('osint', this)" class="btn-comando p-2.5 text-xs rounded">🔍 OSINT Web</button>
        <button onclick="setModo('covid', this)" class="btn-comando p-2.5 text-xs rounded">🏥 Base COVID</button>
        <button onclick="setModo('financial', this)" class="btn-comando p-2.5 text-xs rounded">💳 Financiero</button>
        <button onclick="setModo('ocr', this)" class="btn-comando p-2.5 text-xs rounded">👁️ OCR Visión</button>
        <button onclick="setModo('facial', this)" class="btn-comando p-2.5 text-xs rounded col-span-3">👤 Reconocimiento Facial (Rostro)</button>
    </div>

    <!-- ENTRADA DE DATOS -->
    <div class="panel-tactico p-3.5 mb-4 rounded-lg">
        <div id="inputTextoContainer">
            <label class="block text-[10px] text-gray-400 mb-1 tracking-wider">OBJETIVO DE BÚSQUEDA:</label>
            <input type="text" id="searchInput" placeholder="Ingresa teléfono, nombre completo, CURP o IP..." class="w-full bg-black/60 border border-gray-700 rounded p-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-cyan-400 transition">
        </div>
        
        <div id="inputArchivoContainer" class="hidden mb-1">
            <label class="block text-[10px] text-gray-400 mb-1 tracking-wider">CARGAR ARCHIVO O FOTOGRAFÍA:</label>
            <input type="file" id="fileInput" accept="image/*,.pdf,.doc" class="w-full text-xs text-gray-300 border border-gray-700 rounded p-2 bg-black/60 file:mr-4 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-cyan-950 file:text-cyan-300 hover:file:bg-cyan-900">
        </div>

        <button onclick="ejecutarAnalisis()" class="w-full mt-3 bg-cyan-600 text-black font-extrabold py-2.5 text-xs tracking-wider rounded hover:bg-cyan-500 transition shadow-lg">
            EJECUTAR ANÁLISIS TÁCTICO →
        </button>
    </div>

    <!-- RESULTADO TÁCTICO CON PAGINACIÓN -->
    <div class="panel-tactico p-4 rounded-lg">
        <div class="flex justify-between items-center mb-2 border-b border-gray-800 pb-1.5">
            <h3 class="text-xs font-bold text-gray-300 tracking-wide">RESULTADO DEL SISTEMA</h3>
            <span id="contadorResultados" class="text-[10px] text-cyan-400 font-semibold">0 registros</span>
        </div>
        
        <div id="resultadoTactico" class="text-xs text-gray-200 whitespace-pre-wrap font-mono min-h-[160px] py-1">
            <span class="text-gray-500">[ Sistema en espera de parámetros de consulta... ]</span>
        </div>

        <!-- CONTROLES DE PAGINACIÓN -->
        <div id="paginacionContainer" class="hidden flex justify-between items-center mt-3 pt-2 border-t border-gray-800 text-xs">
            <button onclick="cambiarPagina(-1)" id="btnAnterior" class="px-3 py-1 bg-gray-900 border border-gray-700 text-gray-300 rounded hover:bg-cyan-950">← Anterior</button>
            <span id="lblPagina" class="text-cyan-400 font-semibold text-[11px]">Página 1 de 1</span>
            <button onclick="cambiarPagina(1)" id="btnSiguiente" class="px-3 py-1 bg-gray-900 border border-gray-700 text-gray-300 rounded hover:bg-cyan-950">Siguiente →</button>
        </div>
    </div>

    <!-- NAVEGACIÓN INFERIOR FIJA -->
    <div class="fixed bottom-0 left-0 right-0 bg-black/95 border-t border-cyan-950 p-2.5 flex justify-around text-xs max-w-xl mx-auto backdrop-blur-md">
        <button onclick="location.reload()" class="text-cyan-400 font-bold flex items-center gap-1">🔍 Búsqueda</button>
        <button onclick="toggleHistorial()" class="text-gray-400 hover:text-cyan-400 transition">📁 Historial</button>
        <button onclick="alert('Rango actual: Usuario Free\nCréditos compartidos: 3/10')" class="text-gray-400 hover:text-cyan-400 transition">💎 Tienda VIP</button>
        <button onclick="alert('Operador: Cervando\nID: 6482757502\nNivel de Acceso: Autorizado\nEstado: Conectado')" class="text-gray-400 hover:text-cyan-400 transition">👤 Mi Cuenta</button>
    </div>

    <script>
        let modoActual = 'telcel';
        const userId = 6482757502;
        let resultadosGlobales = [];
        let paginaActual = 1;
        const porPagina = 2; // Cantidad de resultados por página

        function setModo(modo, btn) {
            modoActual = modo;
            document.querySelectorAll('.btn-comando').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            if(modo === 'ocr' || modo === 'facial') {
                document.getElementById('inputTextoContainer').classList.add('hidden');
                document.getElementById('inputArchivoContainer').classList.remove('hidden');
            } else {
                document.getElementById('inputTextoContainer').classList.remove('hidden');
                document.getElementById('inputArchivoContainer').classList.add('hidden');
            }
        }

        async function ejecutarAnalisis() {
            const resultadoBox = document.getElementById('resultadoTactico');
            const paginacionDiv = document.getElementById('paginacionContainer');
            paginacionDiv.classList.add('hidden');

            // Animación de suspenso por fases más realista
            resultadoBox.innerHTML = `<span class="text-cyan-400 animate-pulse">⚡ [ESTABLECIENDO ENLACE SEGURO CON NODO DE RED]...\n█▒▒▒▒▒▒▒▒▒ 15% - Verificando credenciales de operador...</span>`;
            await new Promise(r => setTimeout(r, 450));
            resultadoBox.innerHTML = `<span class="text-cyan-400 animate-pulse">⚡ [EXTRAYENDO METADATOS Y CRUCE DE CELDAS]...\n██████▒▒▒▒ 65% - Procesando registros en bases de datos...</span>`;
            await new Promise(r => setTimeout(r, 550));

            try {
                if (modoActual === 'ocr' || modoActual === 'facial') {
                    const fileInput = document.getElementById('fileInput');
                    if(fileInput.files.length === 0) {
                        alert("Sube un archivo o fotografía válida antes de ejecutar.");
                        resultadoBox.innerHTML = '<span class="text-yellow-400">[!] Error: Ningún archivo seleccionado.</span>';
                        return;
                    }
                    const formData = new FormData();
                    formData.append("file", fileInput.files[0]);
                    const endpoint = modoActual === 'ocr' ? '/api/ocr' : '/api/facial';

                    const res = await fetch(endpoint, { method: 'POST', body: formData });
                    const data = await res.json();
                    
                    resultadosGlobales = [{detalles: data.detalles}];
                    paginaActual = 1;
                    renderizarResultados();
                } else {
                    const query = document.getElementById('searchInput').value;
                    if(!query) {
                        alert("Ingresa un objetivo de búsqueda válido.");
                        resultadoBox.innerHTML = '<span class="text-yellow-400">[!] Error: Parámetro de búsqueda vacío.</span>';
                        return;
                    }

                    const res = await fetch('/api/buscar', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ user_id: userId, query: query, type: modoActual })
                    });
                    const data = await res.json();

                    resultadosGlobales = data.data || [];
                    paginaActual = 1;
                    renderizarResultados();
                }
            } catch (err) {
                resultadoBox.innerHTML = `<span class="text-red-400">⚠️ Error crítico conectando con el servidor de inteligencia.</span>`;
            }
        }

        function renderizarResultados() {
            const resultadoBox = document.getElementById('resultadoTactico');
            const contador = document.getElementById('contadorResultados');
            const paginacionDiv = document.getElementById('paginacionContainer');

            contador.innerText = `${resultadosGlobales.length} registros`;

            if(resultadosGlobales.length === 0) {
                resultadoBox.innerHTML = `<span class="text-yellow-400">⚠️️ Sin coincidencias exactas para este objetivo en el sector consultado.</span>`;
                paginacionDiv.classList.add('hidden');
                return;
            }

            const totalPaginas = Math.ceil(resultadosGlobales.length / porPagina);
            const inicio = (paginaActual - 1) * porPagina;
            const fin = inicio + porPagina;
            const paginaItems = resultadosGlobales.slice(inicio, fin);

            let html = "";
            paginaItems.forEach((item, idx) => {
                const indexReal = inicio + idx + 1;
                html += `
                    <div class="p-3 mb-2.5 border border-cyan-900 bg-black/70 rounded shadow-md">
                        <div class="text-[10px] text-cyan-400 font-bold mb-1 flex justify-between">
                            <span>REGISTRO #${indexReal}</span>
                            <span class="text-gray-400">ESTADO: VERIFICADO</span>
                        </div>
                        <pre class="whitespace-pre-wrap font-mono text-[11px] text-gray-200 leading-relaxed">${item.detalles}</pre>
                    </div>`;
            });

            resultadoBox.innerHTML = html;

            if (totalPaginas > 1) {
                paginacionDiv.classList.remove('flex');
                paginacionDiv.classList.remove('hidden');
                paginacionDiv.classList.add('flex');
                document.getElementById('lblPagina').innerText = `Página ${paginaActual} de ${totalPaginas}`;
                document.getElementById('btnAnterior').disabled = paginaActual === 1;
                document.getElementById('btnSiguiente').disabled = paginaActual === totalPaginas;
            } else {
                paginacionDiv.classList.add('hidden');
            }
        }

        function cambiarPagina(direccion) {
            const totalPaginas = Math.ceil(resultadosGlobales.length / porPagina);
            paginaActual += direccion;
            if(paginaActual < 1) paginaActual = 1;
            if(paginaActual > totalPaginas) paginaActual = totalPaginas;
            renderizarResultados();
        }

        async function toggleHistorial() {
            const panel = document.getElementById('panelHistorial');
            panel.classList.toggle('hidden');
            if(!panel.classList.contains('hidden')) {
                const res = await fetch(`/api/historial/${userId}`);
                const data = await res.json();
                const lista = document.getElementById('listaHistorial');
                if(data.historial && data.historial.length > 0) {
                    lista.innerHTML = data.historial.map(h => `<div class="border-b border-gray-900 py-1 flex justify-between text-[11px]"><span>🔹 [<b>${h.modo}</b>] ${h.query}</span><span class="text-gray-500 text-[10px]">${h.timestamp}</span></div>`).join('');
                } else {
                    lista.innerHTML = `<p class="text-gray-500 text-center py-2">Sin consultas registradas.</p>`;
                }
            }
        }
    </script>
</body>
</html>
