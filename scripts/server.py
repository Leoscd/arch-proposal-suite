"""
server.py — Servidor Flask local para el Arch Proposal Suite
Tarea 6.1: expone los outputs del proyecto como API REST.

Uso: python3 scripts/server.py
     O desde VS Code con la configuración "servidor-obra" en launch.json
"""

import json
import os
from pathlib import Path
from datetime import datetime

from flask import Flask, jsonify, request, abort, send_from_directory
from flask import make_response

# ---------------------------------------------------------------------------
# Configuración de rutas
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
DOCS_DIR = OUTPUTS_DIR / "documentacion"
CERTS_DIR = DOCS_DIR / "certificados"
ESTADO_PATH = OUTPUTS_DIR / "estado-proyecto.json"

app = Flask(__name__, static_folder=str(OUTPUTS_DIR), static_url_path="/static")

# ---------------------------------------------------------------------------
# CORS — permite que dashboards HTML en cualquier origen consuman la API
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response

@app.route("/", methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path=""):
    return make_response("", 204)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_json(path: Path):
    """Lee un archivo JSON y devuelve el dict; 404 si no existe."""
    if not path.exists():
        abort(404, description=f"Archivo no encontrado: {path.name}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _write_json(path: Path, data: dict):
    """Escribe un dict como JSON con formato."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _read_estado() -> dict:
    """Lee estado-proyecto.json; devuelve {} si no existe."""
    if not ESTADO_PATH.exists():
        return {}
    with open(ESTADO_PATH, encoding="utf-8") as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Endpoints GET
# ---------------------------------------------------------------------------
@app.route("/api/estado", methods=["GET"])
def get_estado():
    """Devuelve el estado global del proyecto."""
    return jsonify(_read_json(ESTADO_PATH))


@app.route("/api/cronograma", methods=["GET"])
def get_cronograma():
    """Devuelve el cronograma principal (cronograma.json)."""
    path = OUTPUTS_DIR / "cronograma.json"
    # Fallback al cronograma de obra completa si el simple no existe
    if not path.exists():
        path = OUTPUTS_DIR / "cronograma_obra_completa.json"
    return jsonify(_read_json(path))


@app.route("/api/presupuesto", methods=["GET"])
def get_presupuesto():
    """Devuelve el presupuesto (busca varios nombres posibles)."""
    candidatos = [
        OUTPUTS_DIR / "presupuesto.json",
        OUTPUTS_DIR / "presupuesto_obra_completa.json",
    ]
    for path in candidatos:
        if path.exists():
            return jsonify(_read_json(path))
    abort(404, description="No se encontró ningún archivo de presupuesto.")


@app.route("/api/calendario", methods=["GET"])
def get_calendario():
    """Devuelve el calendario de certificados."""
    return jsonify(_read_json(DOCS_DIR / "calendario_certificados.json"))


@app.route("/api/computo", methods=["GET"])
def get_computo():
    """Devuelve el cómputo de materiales."""
    return jsonify(_read_json(DOCS_DIR / "computo_materiales.json"))


@app.route("/api/certificados", methods=["GET"])
def get_certificados():
    """Lista los archivos disponibles en outputs/documentacion/certificados/."""
    if not CERTS_DIR.exists():
        return jsonify({"certificados": [], "total": 0})
    archivos = sorted(
        f.name for f in CERTS_DIR.iterdir() if f.is_file()
    )
    return jsonify({"certificados": archivos, "total": len(archivos)})

# ---------------------------------------------------------------------------
# Endpoints POST
# ---------------------------------------------------------------------------
@app.route("/api/gasto", methods=["POST"])
def post_gasto():
    """
    Registra un gasto real en estado-proyecto.json["gastos_reales"].

    Body JSON esperado:
        emisor       — str  — quién emitió el comprobante
        fecha        — str  — fecha del gasto (YYYY-MM-DD)
        materiales   — list — lista de materiales involucrados
        monto_ars    — num  — monto en pesos argentinos
        descripcion  — str  — descripción libre
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Body JSON requerido.")

    campos_requeridos = ["emisor", "fecha", "monto_ars"]
    faltantes = [c for c in campos_requeridos if c not in body]
    if faltantes:
        abort(400, description=f"Campos requeridos faltantes: {faltantes}")

    estado = _read_estado()
    if "gastos_reales" not in estado:
        estado["gastos_reales"] = []

    entrada = {
        "id": len(estado["gastos_reales"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "emisor": body.get("emisor"),
        "fecha": body.get("fecha"),
        "materiales": body.get("materiales", []),
        "monto_ars": body.get("monto_ars"),
        "descripcion": body.get("descripcion", ""),
    }
    estado["gastos_reales"].append(entrada)
    _write_json(ESTADO_PATH, estado)

    return jsonify({"ok": True, "gasto_registrado": entrada}), 201


@app.route("/api/avance", methods=["POST"])
def post_avance():
    """
    Registra un avance de obra en estado-proyecto.json["avances"].

    Body JSON esperado:
        semana               — int/str — número de semana
        descripcion          — str     — descripción del avance
        porcentaje_completado — num    — 0 a 100
    """
    body = request.get_json(silent=True)
    if not body:
        abort(400, description="Body JSON requerido.")

    campos_requeridos = ["semana", "descripcion", "porcentaje_completado"]
    faltantes = [c for c in campos_requeridos if c not in body]
    if faltantes:
        abort(400, description=f"Campos requeridos faltantes: {faltantes}")

    estado = _read_estado()
    if "avances" not in estado:
        estado["avances"] = []

    entrada = {
        "id": len(estado["avances"]) + 1,
        "timestamp": datetime.now().isoformat(),
        "semana": body.get("semana"),
        "descripcion": body.get("descripcion"),
        "porcentaje_completado": body.get("porcentaje_completado"),
    }
    estado["avances"].append(entrada)
    _write_json(ESTADO_PATH, estado)

    return jsonify({"ok": True, "avance_registrado": entrada}), 201

# ---------------------------------------------------------------------------
# Manejador de errores JSON
# ---------------------------------------------------------------------------
@app.errorhandler(400)
@app.errorhandler(404)
def handle_error(e):
    return jsonify({"error": str(e.description)}), e.code

# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[servidor-obra] BASE_DIR: {BASE_DIR}")
    print(f"[servidor-obra] Iniciando en http://0.0.0.0:8080")
    print("[servidor-obra] Endpoints disponibles:")
    for rule in [
        "GET  /api/estado",
        "GET  /api/cronograma",
        "GET  /api/presupuesto",
        "GET  /api/calendario",
        "GET  /api/computo",
        "GET  /api/certificados",
        "POST /api/gasto",
        "POST /api/avance",
        "GET  /static/<path>  (outputs/)",
    ]:
        print(f"       {rule}")
    app.run(host="0.0.0.0", port=8080, debug=True)
