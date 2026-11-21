# r3Dy (3D szkennelés AI ágensekkel)

9 órás AI agentic hackathon-projekt, 2 fős csapat. Forgóasztalon fotózott tárgyakból fotogrammetriával textúrázott 3D modell, Blender-utómunka, statikus weboldal előnézettel és GLB/.blend letöltéssel. **A láncot Claude-ágensek vezérlik** – ez a projekt fő újdonsága.

- **Terv, döntések, ütemterv:** `TERV.md` – változáskor frissítendő.
- **Elmélet és működés:** `MUKODES.md` – lépés, parancs, kapcsoló vagy mért szám változásakor frissítendő.
- **Teszt és elvárt kimenetek:** `TESZT.md` – ha a lánc vagy az ágens kimenete, kapcsolói változnak, ezt is.
- `TODO.md` – helyi, git-ignorált ellenőrzőlista (régi azonosítókat sorol fel): **soha ne commitold**, és a tartalmát ne másold a repó más fájljaiba.

Repó: `github.com/molnaristud-arch/r3Dy` (privát), ág `main`. Ebben a mappában a git SSH-n a `github-molnaristud` host aliasszal pushol, a commit-identitás repó-szintű (`molnaristud-arch`). A gép globális git- és `gh`-beállításai egy másik fiókhoz tartoznak – azokat ne módosítsd.

## Ágensek (`agent/`)

- `controller.py` – **vezérlő ágens** (Claude Opus 5.5, adaptív gondolkodás, `display: summarized`, effort `high`, kézi eszközhívási ciklus a Messages API-n, `fallbacks: "default"`). Minden lépés után az eredmény alapján dönt. Korlátok: `MAX_CALLS` eszközönként, `--max-steps` összesen. `--publish` nélkül nem tölt fel. Napló: terminál + `<scan>/agent_log.jsonl`. A döntési támpontok a `SYSTEM_PROMPT`-ban vannak – viselkedést ott hangolj.
- `tools.py` – az eszközök (sémák: `TOOL_SCHEMAS`, megvalósítás: `IMPLS`). Mindegyik egyetlen, induláskor rögzített `data/` alatti mappán dolgozik; a teljes kimenet a `<scan>/agent_run.log`-ba megy, a modell rövid JSON-t (+ képeket) kap. Kézi teszt API nélkül: `.venv/bin/python agent/tools.py data/<scan> <eszköz> '<json>'`.
- `qa.py` – **minőségellenőrző + kurátor ágens** (Claude Sonnet 5.5, `QA_MODEL` env-vel felülírható, JSON-séma structured outputtal): `nev`, `leiras`, `cimkek`, `minoseg` (jo|gyanus|hibas), `hibak`, `javaslat` (+ `model`, `size_cm`). A vezérlő `quality_check` eszköze és az `auto.sh` is ezt hívja. Kilépési kód: 1 nincs beállítva / nincs előnézet, 2 hibás válasz, 3 nem érhető el.
- Kulcs: `ANTHROPIC_API_KEY` a környezetből vagy a git-ignorált `.env`-ből (`controller.load_env`). A `.env`-et soha ne commitold, a kulcsot ne írd ki.
- Új eszköz: séma a `TOOL_SCHEMAS`-ba, függvény az `IMPLS`-be, hívási korlát a `MAX_CALLS`-ba, használati támpont a `SYSTEM_PROMPT`-ba, leírás a `MUKODES.md` 3.3-ba.

## Lánc és fájlok

- `capture/turntable_disc.py` – nyomtatható korong (SVG): 10°-os fokbeosztás + véletlen mintázat (a COLMAP-nak) + 5 cm-es skála.
- `capture/turntable_stepper/` – Arduino-vázlat (28BYJ-48 + ULN2003, D8–D11, zümmer D7, gomb D2): léptető és folyamatos mód. Arduino-fordító nincs a gépen: `capture/stepper_sim/run.sh` g++-szal szimulálja – a vázlat változtatása után futtasd.
- `pipeline/extract_frames.py` – videóból egyenletes időközönként a legélesebb kocka (Laplace-szórás), ablakonként azonnal kiírva.
- `pipeline/mask.py` – háttér kivágása (`rembg`, GPU) → `<scan>/masked`; ha létezik, a `reconstruct.sh` ezt használja.
- `pipeline/reconstruct.sh` – COLMAP (jellemzőpontok, exhaustive matching, mapper, `model_orientation_aligner --method IMAGE-ORIENTATION`, undistort) → OpenMVS (Densify, ReconstructMesh, TextureMesh) → `<scan>/model/model.obj`.
- `blender/run.sh cleanup|preview …` – a Blender-szkriptek indítója (`--python-exit-code 1`, különben a Blender mindig 0-val lép ki). `cleanup.py`: import (`--up NEGATIVE_Y`), legnagyobb darab, decimálás, lépték (`--size` m), talp az origóban, GLB (+ `--blend`). `preview.py`: N nézet PNG-be.
- `pipeline/publish.py` – GLB (+ .blend) → `web/models/<slug>.glb`, bejegyzés a `models.json`-ba.
- `pipeline/auto.sh` – **tartalék**, fix sorrendű lánc ágens nélkül (`--watch`, `--size`, `--mask`, `--frames`, `--no-ai`, …); a végén `agent/qa.py`-tól kér javaslatot. Az élő oldal címe a `SITE` környezeti változó (alap: https://r3dy-web.vercel.app; üres = nem várja meg az élesítést).
- `web/` – statikus oldal, `<model-viewer>@4.0.0`. Éles: **https://r3dy-web.vercel.app** (Vercel-projekt `r3dy-web`, csapat `is2`, Root Directory `web`, preset Other); minden push a `main`-re élesít, csak a `web/` megy ki (ellenőrizve: `/TERV.md`, `/.env` → 404).
- `presentation/` – demóprezentáció (`deck.json`, `deck.css`, `slides/*.html`); `python3 presentation/build.py --pdf` → `prezentacio.html` + `.pdf` (headless Chrome).
- `docs/howto/HowToUse.html` → `HowToUse.pdf` (`./docs/howto/build.sh`, headless Chrome). Parancs vagy kimenet változásakor frissítsd.
- `data/` – git-ignorált, **kivéve** `data/sample/` (11 kép, **AGPL** – belőle készült modellt soha ne publikálj; a `publish_model` md5 alapján tiltja).

## Környezet (MSI GP65: i7-10750H, 16 GB, RTX 2060 6 GB, Ubuntu 26.04)

- COLMAP 4.2.1 + OpenMVS 2.4.0 **CUDA-build** a micromamba `scan` env-ben (`~/.local/bin/micromamba`, root `~/.local/share/micromamba` – a `MAMBA_ROOT_PREFIX`-et a szkriptek és a `tools.py` is beállítják). Az Ubuntu `colmap` csomagja hibás – ne használd.
- Blender 5.0.1 (apt) rendszer-Pythonnal; a numpy-t a `run.sh` a `.venv`-ből adja (`--python-use-system-env`). A `.venv` Pythonja (3.14) egyezzen a Blenderével.
- A `.venv` abszolút útvonalakat tartalmaz: a mappa áthelyezése után `rm -rf .venv && ./setup.sh`.

## Tanulságok (tesztelve)

- OpenMVS 2.4: a `ReconstructMesh` csak `scene_dense_mesh.ply`-t ír → `TextureMesh … --mesh-file scene_dense_mesh.ply`.
- A seam leveling fekete foltokat fest az atlaszra → `--global-seam-leveling 0 --local-seam-leveling 0`.
- Igazítás után a gravitáció `+Y` → import `up_axis=NEGATIVE_Y`. Az importer előre-tengelye `Z`, ezért `up_axis` nem lehet `Z`/`NEGATIVE_Z`.
- 6 GB VRAM: a max képméret 2000.
- A regisztrált képek száma: `colmap model_analyzer --path work/sparse/0` → „Registered images: N”.
- A mintán (11 kép) a vezérlő ágens magától háttérkivágást kért a talaj- és égfoltok miatt, és az eredmény jobb lett (2026-11-21, ~5 perc, 8 lépés).

## Szabályok

- A felület és a dokumentáció magyar; a kódkommentek angolok.
- Commit és push a felhasználó kérésére. Force-push, history-törlés, repó- vagy ágtörlés előtt mindig kérdezz.
- Változtatás után: `bash -n` a shell-szkriptekre, `.venv/bin/python -m py_compile agent/*.py pipeline/*.py`; ágens- vagy láncváltozásnál a mintán (`data/sample` másolatán) végig kell futtatni, és a `preview`-t szemre ellenőrizni.
