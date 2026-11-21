# Projektterv – 3D szkennelés kézi forgóasztallal (vázlat)

**Csapat:** _TBD_ · **Idő:** 9 óra · **Gép:** _TBD (NVIDIA GPU + CUDA)_ · **Repó:** `github.com/molnaristud-arch/r3Dy` (privát) · **Élő oldal:** _TBD_

> Vázlat: csak támpontok. A részleteket menet közben töltjük ki.

## 1. Cél és demó
- Tárgy körbefotózása forgóasztalon → textúrázott 3D modell → Blender-utómunka → weboldal (forgatás, AR, GLB/.blend letöltés)
- Demó (3–4 perc): élő fotózás → automatikus feldolgozás → új modell az oldalon
- B terv: előre szkennelt modell

## 2. Architektúra
- Hardver: forgóasztal + mintás korong, fény, háttér, telefon állványon
- Laptop: képkinyerés → (maszk) → rekonstrukció → Blender cleanup → előnézet → publikálás
- Web: statikus oldal, `git push` = élesítés
- Döntések:
  - fotogrammetria (nem AI-modellezés)
  - COLMAP + OpenMVS
  - nincs felhőtárhely
  - nincs backend

## 3. Hardver
- [ ] Bevásárlólista: forgó alap, tányér, nyomtatott korong (100%), háttér, 2 lámpa + szóró, állvány, BT exponáló
- [ ] Asztal összerakása (korong középen, fix jel, íves háttér, 45°-os fények)
- [ ] Telefon: fókusz/expozíció/fehéregyensúly zárolva, max felbontás, stabilizálás ki
- Felvétel:
  - A mód: fotó 10°-onként, 2–3 magasság, 80–110 kép
  - B mód: videó, ~1 fordulat/perc
- Opcionális: léptetőmotor + Arduino
- Jó tárgyak: matt, mintás, nem átlátszó

## 4. Szoftver
- Környezet: COLMAP (CUDA), OpenMVS (CUDA), Blender, ffmpeg, Python `.venv` (OpenCV, rembg)
- `setup.sh`: ellenőrzés + telepítés
- A lánc lépései:
  1. `extract_frames.py`: videóból éles kockák
  2. `mask.py`: háttérkivágás (opcionális)
  3. `reconstruct.sh`: COLMAP + OpenMVS → OBJ
  4. `blender/run.sh cleanup`: tisztítás, decimálás, méretezés → GLB
  5. `blender/run.sh preview`: előnézeti képek
  6. `publish.py`: `web/models` + `models.json`
  7. `auto.sh --watch`: az egészet vezérli
- `--size`: a tárgy valódi mérete kézzel, méterben
- Ismert csapdák: _TBD_
- Mért futásidők: _TBD_
- Hibakeresési táblázat: _TBD_

## 5. Weboldal
- `<model-viewer>`: kártyarács, forgatás, AR, letöltés (GLB, .blend), keresés, sötét téma
- Adatforrás: `web/models/models.json`
- Hosting: _TBD (új Vercel-projekt, Root Directory `web`)_
- Bővítés:
  - bélyegképek
  - modelloldal
  - több formátum (OBJ, FBX, USDZ)

## 6. AI ügynök (opcionális)
- Név, leírás, címkék, minőségítélet az előnézetekből
- Háttér: _TBD (saját n8n, vagy közvetlen Gemini API a `describe.py`-ból)_
- Csak ha a fő lánc kész

## 7. Kockázatok és B tervek
- Rossz szkennelés → előre kész modellek
- Lassú feldolgozás → előre elkészített modell „befejezése”
- A körök nem illeszkednek → külön szkennelés
- Hiányzik az alj → vállalt korlát
- Nincs internet → offline lánc, helyi webszerver
- Melegedés, tárhely

## 8. Ütemterv (9 óra, 2 fő)
- 0:00–1:30: asztal, setup, első próbaszkennelés
- 1:30–4:00: első teljes lánc → weboldal; 2–3 jó modell
- **4:00 ellenőrzőpont:** legalább 2 modell élesben
- 4:00–7:00: bővítések, `auto.sh` integráció
- **7:00 feature freeze**
- 7:00–9:00: prezentáció, főpróba

## 9. Előzetes teendők
- [ ] Szoftverek telepítése és tesztelése
- [ ] Teljes lánc a mintakészleten
- [ ] Alkatrészek, korong nyomtatása
- [ ] Otthoni próbaszkennelés, futásidő mérése
- [ ] Hosting beállítása
- [ ] Csapattárs meghívása
- [ ] 2–3 demómodell

## 10. Mappaszerkezet
```
r3Dy/
├── TERV.md, README.md, CLAUDE.md
├── setup.sh
├── capture/      korong (SVG), motor
├── pipeline/     auto.sh, extract_frames, mask, reconstruct, publish, describe
├── blender/      run.sh, cleanup.py, preview.py
├── web/          weboldal + models/
└── data/         fotók, köztes eredmények (git-ignorált)
```

## 11. Beüzemelés / újraépítés
- Szabályok: magyar felület és dokumentáció, angol kódkomment; titkok nem kerülnek a repóba
- Külső erőforrások leltára: _TBD_
- Új gépen: klón → apt csomagok → micromamba → `./setup.sh` → mintafuttatás
- Elfogadási lista:
  - [ ] `setup ok`
  - [ ] minta → `KÉSZ`, álló textúrázott modell
  - [ ] AI-javaslat működik (ha van)
  - [ ] saját modell megjelenik az élő oldalon
