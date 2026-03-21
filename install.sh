#!/bin/bash
# =============================================================================
# Arch Proposal Suite — Instalador y lanzador
# Uso desde cualquier directorio: bash <(curl -sL URL)
#   o: git clone ... && cd arch-proposal-suite && bash install.sh
# Compatible: macOS, Linux, WSL (Windows)
# =============================================================================

PORT=8080
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo ""
echo "========================================"
echo "  Arch Proposal Suite — Setup"
echo "========================================"
echo ""

# ── 1. Verificar Python 3 ─────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null && python --version 2>&1 | grep -q "3\."; then
    PYTHON=python
else
    echo -e "${RED}ERROR: Python 3 no encontrado.${NC}"
    echo "Instalá Python 3 desde https://www.python.org/downloads/"
    exit 1
fi
echo -e "${GREEN}✓ Python:${NC} $($PYTHON --version)"

# ── 2. Resolver directorio del proyecto ───────────────────────────────────────
REPO_URL="https://github.com/Leoscd/arch-proposal-suite.git"

# Si ya estamos dentro del repo (existe scripts/server.py), no clonar
if [ -f "scripts/server.py" ]; then
    echo -e "${GREEN}✓ Proyecto detectado en directorio actual${NC}"
    PROJECT_DIR="."
elif [ -d "arch-proposal-suite/scripts" ]; then
    echo -e "${GREEN}✓ Proyecto ya clonado — actualizando...${NC}"
    git -C arch-proposal-suite pull --ff-only 2>/dev/null || true
    PROJECT_DIR="arch-proposal-suite"
else
    echo "Clonando repositorio..."
    git clone "$REPO_URL"
    echo -e "${GREEN}✓ Repositorio clonado${NC}"
    PROJECT_DIR="arch-proposal-suite"
fi

cd "$PROJECT_DIR"

# ── 3. Instalar dependencias ───────────────────────────────────────────────────
echo ""
echo "Instalando dependencias..."

# Intentar con venv primero, si falla usar pip directo
USE_VENV=false
if $PYTHON -m venv --help &>/dev/null 2>&1; then
    if [ ! -d ".venv" ]; then
        $PYTHON -m venv .venv 2>/dev/null && USE_VENV=true || USE_VENV=false
    else
        USE_VENV=true
    fi
fi

if [ "$USE_VENV" = true ]; then
    [ -f ".venv/bin/activate" ] && source .venv/bin/activate
    [ -f ".venv/Scripts/activate" ] && source .venv/Scripts/activate
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencias instaladas (entorno virtual)${NC}"
else
    # Sin venv — pip directo (--user para no necesitar sudo)
    echo -e "${YELLOW}⚠ Sin entorno virtual — instalando con pip --user${NC}"
    $PYTHON -m pip install -q --user -r requirements.txt 2>/dev/null || \
    $PYTHON -m pip install -q -r requirements.txt 2>/dev/null || {
        echo -e "${RED}ERROR: No se pudieron instalar las dependencias.${NC}"
        echo "Intentá manualmente: pip3 install flask Pillow"
        exit 1
    }
    echo -e "${GREEN}✓ Dependencias instaladas${NC}"
fi

# ── 4. Verificar Flask ─────────────────────────────────────────────────────────
$PYTHON -c "import flask" 2>/dev/null || {
    echo -e "${RED}ERROR: Flask no disponible. Instalá con: pip3 install flask${NC}"
    exit 1
}
echo -e "${GREEN}✓ Flask disponible${NC}"

# ── 5. Inicializar archivos si no existen ─────────────────────────────────────
mkdir -p outputs/documentacion/certificados outputs/snapshots

if [ ! -f "outputs/sesion_activa.json" ]; then
    printf '{\n  "rubros_seleccionados": [],\n  "modo_alcance": "obra_completa",\n  "alcance_descripcion": "",\n  "fecha_sesion": "",\n  "personal": { "oficiales": 3, "ayudantes": 3 }\n}\n' > outputs/sesion_activa.json
    echo -e "${GREEN}✓ sesion_activa.json creado${NC}"
fi

if [ ! -f "outputs/cronograma.json" ]; then
    echo "Generando cronograma inicial..."
    $PYTHON scripts/generate_schedule.py 2>/dev/null && \
        echo -e "${GREEN}✓ Cronograma generado${NC}" || \
        echo -e "${YELLOW}⚠ Cronograma no generado — se puede generar después${NC}"
fi

if [ ! -f "outputs/documentacion/calendario_certificados.json" ]; then
    echo "Generando calendario..."
    $PYTHON scripts/generate_calendario.py 2>/dev/null && \
        echo -e "${GREEN}✓ Calendario generado${NC}" || true
fi

# ── 6. Lanzar servidor ─────────────────────────────────────────────────────────
echo ""
echo "========================================"
echo -e "${GREEN}  ¡Sistema listo! Servidor en puerto $PORT${NC}"
echo "========================================"
echo ""
echo -e "  Dashboard Director de Obra : ${YELLOW}http://localhost:$PORT/static/dashboard_arquitecto.html${NC}"
echo -e "  Dashboard Cliente/Inversor : ${YELLOW}http://localhost:$PORT/static/dashboard_inversor.html${NC}"
echo -e "  API estado                 : ${YELLOW}http://localhost:$PORT/api/estado${NC}"
echo ""
echo "  Presioná Ctrl+C para detener."
echo ""

# Abrir browser según SO (no bloquea el script)
URL="http://localhost:$PORT/static/dashboard_arquitecto.html"
{ sleep 2 && {
    command -v xdg-open &>/dev/null && xdg-open "$URL" ||
    command -v open      &>/dev/null && open "$URL"     ||
    command -v explorer.exe &>/dev/null && explorer.exe "$URL" ||
    true
}; } &

$PYTHON scripts/server.py
