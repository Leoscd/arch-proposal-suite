---
name: deploy-github
description: Skill de publicación del Arch Proposal Suite. Publica la landing page del proyecto en GitHub Pages para que el cliente o inversor pueda acceder desde una URL pública. Se llama desde la FASE 5 del workflow cierre_semana.md, después de que el director de obra aprueba la publicación. Verifica en cascada todos los prerrequisitos de GitHub antes de hacer el deploy.
---

# Deploy GitHub — Publicador de Dashboard del Cliente

Este skill es el último eslabón del workflow `/cierre-semana`. Toma el HTML generado por `build_landing.py` y lo publica en GitHub Pages, dejando disponible una URL pública para el cliente o inversor.

## Contexto de ejecución

Sos llamado desde **FASE 5 del workflow `cierre_semana.md`**, después de que:
1. Se generó el certificado de la semana (`outputs/certificado_semana_N.md`)
2. Se guardó el snapshot (`outputs/snapshots/semana_N.json`)
3. `agente-inversor` compiló la landing con `python3 scripts/build_landing.py`
4. El director de obra **aprobó explícitamente** la publicación

Si el director no aprobó, no ejecutes este skill.

---

## CHECK 1 — GitHub CLI instalado

```bash
gh --version
```

**Si falla:** detenete y avisá:
```
❌ GitHub CLI no está instalado.
Por favor instalalo desde: https://cli.github.com/
Luego volvé a ejecutar /cierre-semana para publicar.
```

---

## CHECK 2 — Usuario autenticado en GitHub

```bash
gh auth status
```

**Si no está autenticado:** guiá el login interactivo:
```
🔐 Necesitás autenticarte en GitHub.
Ejecutaré: gh auth login

Seguí los pasos:
  1. Seleccioná "GitHub.com"
  2. Seleccioná "HTTPS"
  3. Autenticá via browser (te abrirá una ventana)
```
Ejecutá `gh auth login` y esperá confirmación antes de continuar.

---

## CHECK 3 — Repositorio remoto configurado

```bash
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" remote -v
```

**Si no hay remote configurado:** preguntá al usuario:
```
📁 No hay repositorio remoto configurado para este proyecto.
¿Querés crear uno nuevo en GitHub?

Nombre sugerido: arch-proposal-suite (o el que prefieras)
Visibilidad: público (necesario para GitHub Pages gratuito)

¿Confirmas? [s/n]
```

Si confirma, ejecutá:
```bash
gh repo create [nombre] --public --description "Arch Proposal Suite — Dashboard de obra"
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" remote add origin https://github.com/[usuario]/[nombre].git
```

---

## CHECK 4 — Rama gh-pages existe

```bash
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" branch -a | grep gh-pages
```

**Si no existe:** creala con un commit inicial vacío:
```bash
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" checkout --orphan gh-pages
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" reset --hard
echo "# Dashboard" > index.html
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" add index.html
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" commit -m "init: gh-pages branch"
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" push origin gh-pages
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" checkout -
```

---

## CHECK 5 — GitHub Pages habilitado en el repo

```bash
gh api repos/{owner}/{repo} --jq '.has_pages'
```

**Si devuelve `false`:** activá Pages desde la rama gh-pages:
```bash
gh api repos/{owner}/{repo}/pages \
  --method POST \
  --field source[branch]=gh-pages \
  --field source[path]=/
```

Avisá al usuario:
```
⚙️ GitHub Pages fue activado. La primera vez puede demorar 2-3 minutos en estar disponible.
```

---

## DEPLOY — Publicar la landing

Una vez que los 5 checks pasaron, ejecutá el deploy:

### Paso A — Leer el snapshot de la semana para el mensaje de commit
```bash
cat "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite/outputs/snapshots/semana_N.json"
```
Extraé: `semana`, `semaforo`, `resumen_financiero.gastado_semana_ars`.

### Paso B — Copiar el HTML a gh-pages y hacer push
```bash
# Guardar el HTML generado
CP_SRC="/mnt/d/Soy Leo/agentes-group/arch-proposal-suite/outputs/landing/index.html"

# Cambiar a gh-pages, copiar y pushear
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" checkout gh-pages
cp "$CP_SRC" "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite/index.html"
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" add index.html
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" commit -m "Cierre Semana [N] — Semáforo: [SEMAFORO] — Gasto: $[MONTO ARS]"
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" push origin gh-pages
git -C "/mnt/d/Soy Leo/agentes-group/arch-proposal-suite" checkout -
```

### Paso C — Obtener y mostrar la URL pública
```bash
gh api repos/{owner}/{repo}/pages --jq '.html_url'
```

---

## Mensaje final al director de obra

```
✅ Dashboard publicado exitosamente

🌐 URL del cliente: https://[usuario].github.io/[repo]
📅 Semana:          [N]
💰 Gasto semana:    $ [monto ARS]
🚦 Semáforo:        [VERDE / AMARILLO / ROJO]

El cliente puede acceder desde cualquier dispositivo sin login.
La página se actualizará automáticamente cada vez que se ejecute /cierre-semana.

¿Querés que le envíe la URL al cliente por algún medio? (Notion / mensaje)
```

---

## Diagrama de la cadena completa

```
/cierre-semana
    └─ FASE 5 → agente-inversor
                    ├─ python3 scripts/build_landing.py  (genera HTML)
                    └─ skill: deploy-github
                              ├─ CHECK 1: gh CLI instalado
                              ├─ CHECK 2: gh auth status
                              ├─ CHECK 3: remote repo configurado
                              ├─ CHECK 4: rama gh-pages existe
                              ├─ CHECK 5: GitHub Pages habilitado
                              └─ DEPLOY: push → https://usuario.github.io/repo
```
