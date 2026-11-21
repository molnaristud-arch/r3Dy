# r3Dy

Forgóasztalon körbefotózott tárgyból textúrázott 3D modell. A feldolgozást **AI ágensek vezérlik**: a fotogrammetriás lánc lépései az eszközeik, és minden lépés után ők döntenek a folytatásról. Részletek: [TERV.md](TERV.md).

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

## Felépítés

```
agent/       controller.py (vezérlő ágens), tools.py (az eszközei)
pipeline/    extract_frames, mask, reconstruct.sh, publish, auto.sh (tartalék lánc)
blender/     run.sh, cleanup.py, preview.py
capture/     nyomtatható korong (SVG), léptetőmotor (Arduino)
web/         statikus weboldal (model-viewer) + models/
data/        szkennelések (git-ignorált), kivéve data/sample
```
