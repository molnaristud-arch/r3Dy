# Projektterv – 3D szkennelés kézi forgóasztallal (vázlat)

**Csapat:** _TBD_ · **Idő:** 9 óra · **Gép:** MSI GP65 (i7-10750H, 16 GB RAM, RTX 2060 6 GB, Ubuntu 26.04) · **Repó:** `github.com/molnaristud-arch/r3Dy` (privát) · **Élő oldal:** https://r3dy-web.vercel.app

> Vázlat: csak támpontok. A részleteket menet közben töltjük ki.

## 1. Cél és demó
- Tárgy körbefotózása forgóasztalon → textúrázott 3D modell → Blender-utómunka → weboldal (forgatás, AR, GLB/.blend letöltés)
- Demó (3–4 perc): élő fotózás → automatikus feldolgozás → új modell az oldalon
- B terv: előre szkennelt modell

## 2. Architektúra
- Hardver: forgóasztal + mintás korong, fény, háttér, telefon állványon
- Laptop: képkinyerés → (maszk) → rekonstrukció → Blender cleanup → előnézet → publikálás
- Web: statikus oldal, `git push` = élesítés
### 2.1 Működés ágensekkel (vázlat)

```
   FOTÓZÁS                          FELDOLGOZÁS                                   WEB
┌────────────┐  képek   ┌─────────────────────────────────────────────┐  push  ┌──────────┐
│ forgóasztal│─────────▶│              VEZÉRLŐ ÁGENS                  │───────▶│ weboldal │
│  + telefon │          │   (Claude: lépés → eredmény → döntés)       │        │ + ágens- │
└─────▲──────┘          │                                             │        │  napló   │
      │ „még 4 kép      │  eszközök:  extract_frames  mask            │        └──────────┘
      │  felülről”      │             reconstruct     cleanup         │
┌─────┴──────┐          │             preview         publish         │
│ FOTÓZÁSI   │◀─képek───│                                             │
│ SEGÍTŐ     │          │  szakértők:  ┌────────────────┐ ┌─────────┐ │
└────────────┘          │              │ MINŐSÉG-       │ │ BLENDER │ │
                        │              │ ELLENŐRZŐ      │ │ ÁGENS   │ │
                        │              └───────┬────────┘ └────┬────┘ │
                        │                ítélet│ + javaslat    │ javított GLB
                        │                      ▼               ▼      │
                        │              ┌────────────────────────────┐ │
                        │              │ KURÁTOR: név, címkék, méret │ │
                        │              └────────────────────────────┘ │
                        └─────────────────────────────────────────────┘
```

**1. Fotózás:** a képek a `data/bejovo/`-be érkeznek; a fotózási segítő mindegyiket ellenőrzi, és visszaszól.
```
[segítő] 34/36 kép rendben. A 12. kép elmosódott, készíts helyette újat.
[segítő] Gyors előzetes rekonstrukció: hiányzik a felülnézet 120–200° között.
         → Emeld meg a telefont kb. 60°-ra, és fotózz még 4 képet.
```

**2. Feldolgozás:** a vezérlő minden lépés után dönt.
```
[vezérlő] reconstruct(max=2000) → 71/96 kép regisztrálva.
[vezérlő] Döntés: a 25 kiesett kép nagy része háttérmintás. Újrapróbálom maszkolással.
[vezérlő] mask() → reconstruct(max=2000) → 94/96 kép regisztrálva. ✓
[vezérlő] cleanup(faces=50000) → preview()
```

**3. Minőségellenőrzés:** hiba esetén a vezérlő javíttat.
```
[minőség] Ítélet: GYANÚS. A modell kb. 15°-ban dől, a talp alatt korongdarab maradt.
[vezérlő] Döntés: átadom a Blender ágensnek.
[blender] Tájolás javítva, talp levágva z=0-nál.
          Méretezés a korong 5 cm-es skálájából → 23,4 cm.
[minőség] Ítélet: RENDBEN. ✓
```

**4. Közzététel:**
```
[kurátor] Név: „Festett fa madár” · Címkék: fa, figura, madár, kézműves
[vezérlő] publish() → git push → ÉLES (18 s)
```

- **Demó:** bal oldalon az ágensek élő naplója, jobb oldalon a weboldal. Kulcsjelenet: egy szándékosan rossz szkennelést az ágens felismer és kijavít.
- **Biztonsági háló:** minden döntésnek felső határa van (max. N újrapróbálkozás); ha az ágens elakad, a fix sorrendű `auto.sh` is lefuttatja a láncot.

### 2.2 Döntések
- fotogrammetria (nem AI-modellezés)
- COLMAP + OpenMVS
- nincs felhőtárhely
- nincs backend

## 3. Hardver
- [x] Forgóasztal: Arduino Nano + ULN2003 + 5 V léptetőmotor, 10°-os lépések (zümmer nincs, kézzel exponálunk)
- [ ] Kellékek: nyomtatott korong (100%), háttér, 2 lámpa + szóró, telefontartó / állvány
- [ ] Asztal összerakása (korong középen, fix jel, íves háttér, 45°-os fények)
- [ ] Telefon: fókusz/expozíció/fehéregyensúly zárolva, max felbontás, stabilizálás ki
- Felvétel (a használt mód): a motor 10°-onként lép és megáll, **minden megállásnál kézzel exponálunk**; 2 kör (≈20° és ≈45°), ~72 kép
  - tartalék: kézi forgatás 10°-os jelekkel, vagy videó ~1 fordulat/perc
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
- Ismert csapdák: `CLAUDE.md` „Tanulságok”, `MUKODES.md` 4.2
- Mért futásidők: minta (11 kép) lánc ~75 s; ugyanez a vezérlő ágenssel, egy maszkolásos javítással ~5 perc (8 lépés). Valódi, 72 fotós szkennelés: _még mérendő_ (becslés 8–20 perc)
- Hibakeresési táblázat: `TESZT.md` „Ha valami nem sikerül”

## 5. Weboldal
- `<model-viewer>`: kártyarács, forgatás, AR, letöltés (GLB, .blend), keresés, sötét téma
- Adatforrás: `web/models/models.json`
- Hosting: Vercel, projekt `r3dy-web` (csapat `is2`), Root Directory `web`, minden push a `main`-re élesít → https://r3dy-web.vercel.app
- Bővítés:
  - bélyegképek
  - modelloldal
  - több formátum (OBJ, FBX, USDZ)

## 6. AI ágensek (a projekt középpontja)
- Alapelv: **az ágens vezérel, a szkriptek az eszközei** (az `auto.sh` fix sorrendje helyett)
- Háttér: Claude API eszközhívással, egy Python-ciklusban (`agent/`); külön n8n-szerver nem kell
  - gyakori ellenőrzések: Sonnet 5.5
  - döntések és tervezés: Opus 5.5
- Minden döntés és indoklás naplózva, és a demón élőben látható (terminál / weboldal)

### 6.1 Vezérlő ágens – a gerinc (1. prioritás) ✅ kész: `agent/controller.py`
- Eszközök: `extract_frames`, `mask`, `reconstruct`, `cleanup`, `preview`, `publish`
- Minden lépés után: napló + köztes eredmény → döntés a következő lépésről
- Önjavítás, példák:
  - kevés regisztrált kép → újrafuttatás maszkolással
  - CUDA OOM → kisebb max képméret
  - a körök nem illeszkednek → külön szkennelések
- Leállási feltétel: minőségellenőrző „rendben”, vagy max. N próbálkozás

### 6.2 Minőségellenőrző ágens (1. prioritás) ✅ kész: `agent/qa.py` (`quality_check` eszköz)
- Előnézetek vs. eredeti fotók (vision)
- Kimenet: ítélet (rendben / gyanús / hibás) + konkrét hiba + javasolt javítás
- Visszacsatol a vezérlőnek → önjavító kör

### 6.3 Fotózási segítő ágens (2. prioritás, demó)
- Beérkező képek: elmosódás, expozíció, kéz a képen
- Gyors előzetes rekonstrukcióból: hiányzó szögtartományok
- Utasítás az operátornak (szöveg, opcionálisan hang): „Hiányzik a felülnézet 120–200° között, még 4 kép magasabbról”

### 6.4 Blender ágens (3. prioritás)
- `bpy` kódot ír és futtat: tájolás, lyukak zárása, talp, forgáspont
- Méretezés a korong 5 cm-es skálájából → nincs kézi `--size`
- Ellenőrzés renderrel a javítás után

### 6.5 Kurátor ágens (kis bővítés) ✅ kész: a `quality_check` írja a nevet, leírást, címkéket
- Név, leírás, címkék, kategória → `models.json`
- Opcionálisan: LOD-ok, ütközési háló, valós méret ellenőrzése

### 6.6 Weboldal-chat ágens (ha marad idő)
- Keresés és konverzió természetes nyelven („fából készült tárgy, FBX-ben, Unityhez”)
- Backend kell hozzá

## 7. Kockázatok és B tervek
- Rossz szkennelés → előre kész modellek
- Lassú feldolgozás → előre elkészített modell „befejezése”
- A körök nem illeszkednek → külön szkennelés
- Hiányzik az alj → vállalt korlát
- Nincs internet → offline lánc, helyi webszerver
- Melegedés, tárhely

## 8. Ütemterv (9 óra, 2 fő)
**A** = hardver + felvétel, **B** = szoftver + ágensek

| idő | A | B |
|---|---|---|
| 0:00–1:00 | asztal, korong, fény, háttér | setup ellenőrzése; ágens-váz: Claude API + eszközök a meglévő szkriptekre |
| 1:00–2:00 | 1. próbaszkennelés | első teljes lánc kézzel → GLB → weboldal |
| 2:00–3:30 | felvételi technika finomítása; 2–3 jó szkennelés | **vezérlő ágens** (6.1): a lánc végig ágenssel fut |
| **3:30** | **ellenőrzőpont:** legalább 2 modell élesben, a vezérlő ágens végigfut | |
| 3:30–5:00 | további tárgyak; szándékosan rossz szkennelés a teszthez | **minőségellenőrző** (6.2) + önjavító kör |
| **5:00** | **ellenőrzőpont:** a rossz szkennelést az ágens felismeri és javítja | |
| 5:00–6:30 | fotózási segítő kipróbálása élesben | **fotózási segítő** (6.3); méretezés a skálából (6.4) |
| 6:30–7:00 | demó-tárgy kiválasztása | ágens-napló megjelenítése a demóhoz; kurátor (6.5) |
| **7:00** | **feature freeze: csak hibajavítás** | |
| 7:00–8:00 | prezentáció (hangsúly: az ágensek döntései) | utolsó modellek, README |
| 8:00–9:00 | főpróba ×2, tartalék modellek | |

## 9. Előzetes teendők
- [x] Szoftverek telepítése és tesztelése (`setup ok`, 2026-11-21)
- [x] Teljes lánc a mintakészleten, az ágens eszközein keresztül (~75 s, 2026-11-21)
- [x] Vezérlő ágens első változata: `agent/controller.py` + `agent/tools.py`
- [x] Minőségellenőrző + kurátor ágens: `agent/qa.py`; a tartalék `auto.sh` is ezt használja
- [x] Dokumentáció: `MUKODES.md`, `TESZT.md`, `CLAUDE.md`, `HowToUse.pdf`; prezentáció: `presentation/prezentacio.pdf`
- [ ] Alkatrészek, korong nyomtatása
- [ ] Otthoni próbaszkennelés, futásidő mérése
- [x] Hosting beállítása: https://r3dy-web.vercel.app (2026-11-21)
- [ ] Csapattárs meghívása
- [ ] 2–3 demómodell
- [x] Claude API-kulcs, a kulcs a `.env`-ben (git-ignorálva)
- [ ] 1–2 szándékosan hibás szkennelés az önjavító kör teszteléséhez

## 10. Mappaszerkezet
```
r3Dy/
├── TERV.md, README.md, CLAUDE.md
├── setup.sh
├── capture/      korong (SVG), motor
├── agent/        ágensek: vezérlő, minőségellenőrző, fotózási segítő, Blender, kurátor
├── pipeline/     auto.sh, extract_frames, mask, reconstruct, publish (az ágensek eszközei)
├── blender/      run.sh, cleanup.py, preview.py
├── web/          weboldal + models/
└── data/         fotók, köztes eredmények (git-ignorált)
```

## 11. Beüzemelés / újraépítés
- Szabályok: magyar felület és dokumentáció, angol kódkomment; titkok nem kerülnek a repóba
- Külső erőforrások leltára:
  - GitHub: `molnaristud-arch/r3Dy` (privát), csapattárs írási joggal
  - Vercel: csapat `is2`, projekt `r3dy-web`, Root Directory `web` → https://r3dy-web.vercel.app
  - Claude API: kulcs a git-ignorált `.env`-ben (`ANTHROPIC_API_KEY`); modellek: Opus 5.5 (vezérlő), Sonnet 5.5 (minőségellenőrző)
- Új gépen: klón → apt csomagok → micromamba → `./setup.sh` → mintafuttatás
- Elfogadási lista:
  - [ ] `setup ok`
  - [ ] minta → `KÉSZ`, álló textúrázott modell
  - [ ] AI-javaslat működik (ha van)
  - [ ] saját modell megjelenik az élő oldalon
