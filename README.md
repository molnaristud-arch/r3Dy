# r3Dy

> **English summary (Agentic AI Hackathon 2026, team DIsc – Kozma Dávid, Molnár István)**
>
> r3Dy turns a real object into a textured, true-size 3D model on a public website. An Arduino turntable (Nano + ULN2003 + 5 V stepper) rotates the object in 10° steps and stops; at every stop we take a photo by hand with a fixed phone (~72 photos, two heights); photogrammetry (COLMAP + OpenMVS, CUDA) and Blender build the model. **The pipeline is run by AI agents, not a fixed script:** a *controller agent* (Claude Opus 5.5, tool use – `agent/controller.py`) calls each step as a tool, reads the result (registered-image ratio, error class, preview renders) and decides the next step – retry with background masking, smaller images, another orientation, or publish. An independent *quality-check agent* (Claude Sonnet 5.5, structured JSON – `agent/qa.py`) compares the renders with a real photo, gives a verdict and writes the name, description and tags.
>
> - **Pitch deck:** [presentation/r3Dy-pitch.pptx](presentation/r3Dy-pitch.pptx) · **Live site:** https://r3dy-web.vercel.app
> - **Real runs with the agents' decision logs:** [examples/](examples/)
> - Detailed docs (Hungarian): plan `TERV.md`, how it works `MUKODES.md`, test `TESZT.md`, user guide `HowToUse.pdf`.

Forgóasztalon körbefotózott tárgyból textúrázott 3D modell. A feldolgozást **AI ágensek vezérlik**: a fotogrammetriás lánc lépései az eszközeik, és minden lépés után ők döntenek a folytatásról. Részletek: [TERV.md](TERV.md).

**Élő oldal:** https://r3dy-web.vercel.app

## Telepítés (Ubuntu, NVIDIA GPU)

```bash
sudo apt install -y ffmpeg blender python3-venv
curl -sSfL https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xj -C ~/.local bin/micromamba
./setup.sh                      # elvárt vége: "setup ok"
echo 'ANTHROPIC_API_KEY=...' > .env   # Claude API-kulcs; a .env git-ignorált
```

## Használat

```bash
# Ágens-vezérelt feldolgozás (ajánlott)
.venv/bin/python agent/controller.py --inbox --size 0.28            # data/bejovo/ → data/modell_N
.venv/bin/python agent/controller.py data/modell_1 --publish        # meglévő szkennelés, feltöltéssel

# Egy eszköz kézi kipróbálása (API nélkül)
.venv/bin/python agent/tools.py data/modell_1 scan_info

# Tartalék: fix sorrendű lánc, ágens nélkül
./pipeline/auto.sh --watch --size 0.28
```

A `--publish` nélkül az ágens nem tölt fel semmit. A `data/sample` tesztkészlet AGPL-licencű: belőle készült modellt nem szabad közzétenni (az ágens ezt ellenőrzi).

## Dokumentáció

- [TERV.md](TERV.md) – terv, döntések, ütemterv
- [MUKODES.md](MUKODES.md) – elmélet és a lánc működése lépésről lépésre
- [TESZT.md](TESZT.md) – teljes teszt elvárt kimenetekkel
- [HowToUse.pdf](HowToUse.pdf) – használati útmutató (forrás: `docs/howto/`)
- [presentation/prezentacio.pdf](presentation/prezentacio.pdf) – demóprezentáció (forrás: `presentation/`, `build.py --pdf`)
- [presentation/r3Dy-pitch.pptx](presentation/r3Dy-pitch.pptx) – angol pitch (6 dia, a beadáshoz)
- [examples/](examples/) – valódi szkennelések: az ágensek döntési naplója, ítélete, előnézetek

## Felépítés

```
agent/       controller.py (vezérlő ágens), tools.py (az eszközei), qa.py (minőségellenőrző ágens)
pipeline/    extract_frames, mask, reconstruct.sh, publish, auto.sh (tartalék lánc)
blender/     run.sh, cleanup.py, preview.py
capture/     nyomtatható korong (SVG), léptetőmotor (Arduino)
web/         statikus weboldal (model-viewer) + models/
presentation/ demóprezentáció · docs/howto/ az útmutató forrása
data/        szkennelések (git-ignorált), kivéve data/sample
```
