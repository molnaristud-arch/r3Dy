# Teljes teszt – lépésről lépésre, elvárt eredményekkel

## Hogyan működik most

```
 [forgóasztal: Arduino Nano]     [telefon, rögzítve]             [laptop]
  10°-ot fordul, megáll       →   mi exponálunk kézzel     →     USB: DCIM/… → data/bejovo/
  ("FOTO k/36")                   minden megállásnál                         │
                                                                             ▼
                      .venv/bin/python agent/controller.py --inbox --size 0.24
                        vezérlő ágens (Claude): minden lépés után dönt
                          scan_info → reconstruct → cleanup_model → render_preview
                          → quality_check (független minőségellenőrző ágens)
                          → szükség esetén javít (háttérkivágás, kisebb képméret, más tájolás) és újraellenőriz
                          → publish_model (csak --publish esetén) → git push
                                                                             │
                                                                             ▼
                                                  Vercel élesít (~20 s) → https://r3dy-web.vercel.app
```

Tartalék, ha az ágens nem használható (pl. nincs internet): `./pipeline/auto.sh --watch --size 0.24` – ugyanaz a lánc, fix sorrendben.

A teszt öt szintből áll. Egymásra épülnek: ha egy szint nem megy, javítsátok, mielőtt a következőbe kezdtek.

| szint | mit ellenőriz | kell hozzá | idő |
|---|---|---|---|
| 1 | a szoftverlánc és az ágensek a gépen | csak a laptop + API-kulcs | 10 perc |
| 2 | motor + Arduino | Arduino Nano, ULN2003, motor | 10 perc |
| 3 | próbakör kézi exponálással | + telefon | 5 perc |
| 4 | **teljes szkennelés a weboldalig** | minden + egy tárgy | 30–45 perc |
| 5 | **az önjavító kör** (a demó kulcsjelenete) | szándékosan rossz szkennelések | 30–60 perc |

A 2–3. szint kihagyható, ha motor nélkül, kézzel forgattok.

---

## 1. szint – szoftver és ágensek, mintaképekkel (hardver nélkül)

```bash
cd "$HOME/Documents/cursor/Hackathon 2026"
./setup.sh
mkdir -p data/teszt_minta/images && cp data/sample/images/*.jpg data/teszt_minta/images/
.venv/bin/python agent/tools.py data/teszt_minta scan_info             # API nélkül
.venv/bin/python agent/controller.py data/teszt_minta --size 0.3       # közzététel nélkül
```

**Elvárt eredmény:**
- `setup.sh` végén: `COLMAP 4.2.1…`, `OpenMVS…`, `Blender 5.0.1`, `opencv … | onnxruntime ['TensorrtExecutionProvider', 'CUDAExecutionProvider']`, `setup ok`.
- `scan_info`: `"images": 11`.
- A vezérlő naplója: `[vezérlő] Döntés: …` sorok, `reconstruct` → `"registered_images": 11`, majd `cleanup_model`, `render_preview`, `quality_check`. Az ágens jellemzően észreveszi a modellen maradt talajt és eget, háttérkivágást kér, újrarekonstruál, és összeveti az eredményt. A végén **`[kész] KÉSZ (… perc, … lépés)`** és egy magyar összefoglaló (kb. 3–6 perc).
- `data/teszt_minta/preview/view_0.png`: **egyenesen álló, textúrázott kastélyhomlokzat.**

**Takarítás:** `rm -rf data/teszt_minta`. A minta AGPL-licencű, **nem kerülhet fel az oldalra** – az ágens ezt amúgy is tiltja.

**Ha `[hiba] Érvénytelen vagy hiányzó ANTHROPIC_API_KEY`:** a `.env` fájlban `ANTHROPIC_API_KEY=sk-ant-…` sornak kell lennie (lásd README).

---

## 2. szint – motor és Arduino (telefon nélkül)

Bekötés, feltöltés: [`capture/turntable_stepper/README.md`](capture/turntable_stepper/README.md). Ragassz egy szalagdarabot a tányér szélére, és egy másikat mellé az asztalra (fix jel). Hardver nélküli előteszt: `capture/stepper_sim/run.sh` (elvárt: 36 fotó 9,98–10,07°-onként, ~122 s; CONT 60 s alatt 1,000 fordulat).

Arduino IDE → Serial Monitor, 115200 baud, „Newline”:

| beírod | elvárt eredmény |
|---|---|
| (feltöltés után) | `Forgoasztal kesz. Gomb vagy 's' = …` |
| `?` | `mod=IDLE n=36 d=2500 r=1.00 b=1 foto=0` |
| `n4` majd `d1000` | `n=4`, `d=1000` az állapotsorban |
| `s` | 4 megállás, 90°-onként: `FOTO 1/4` … `FOTO 4/4`, majd `KESZ: egy teljes kor…` (sípszó csak zümmerrel lenne – nálunk nincs) |
| `c` | `START: folyamatos, 1.00 RPM`. **A szalagjel pontosan 60 s (±1 s) alatt ér körbe.** |
| `x` | `STOP`, a tányér azonnal megáll |
| gomb | megnyomva elindul a léptető mód, újra megnyomva leáll (`STOP (gomb)`) |
| `n36` majd `d2500` | vissza az alapértékekre |

**Hibás, ha:** a motor csak zúg vagy rezeg, de nem forog: az IN1–IN4 sorrend rossz (D8–D11-re kell kötni őket). A forgásirány mindegy.

---

## 3. szint – próbakör kézi exponálással

1. A telefon rögzítve (állvány / tartó / könyvkupac), 40–50 cm-re, kb. 20°-kal a tárgy fölött.
2. Ugyanaz a beállítás, mint a valódi szkennelésnél: legnagyobb felbontás, zárolt fókusz és expozíció, fix fehéregyensúly, HDR, vaku, éjszakai mód kikapcsolva, 1× zoom. iPhone-on JPG formátum (Beállítások → Kamera → Formátumok → Legkompatibilisebb).
3. Serial Monitorban: `n4`, majd `s`. **Minden megállásnál** (`FOTO k/4`): fél másodperc várakozás, majd egy finom érintés az exponálógombon.

**Elvárt eredmény:** **4 új fotó**, mindegyik éles, a tárgy mindegyiken ugyanott van a képen, és a tányér mindegyiken más szögben áll.

- **Elmosódott kép / elmozdult a telefon az érintéstől:** 2 s-os önkioldó a kamerában, és hosszabb állás: `d4000`; vagy hangerőgomb / távkioldó.
- **Nem érsz oda időben:** `d4000`–`d6000` (a Nano újraindítás után visszaáll 2,5 s-ra, ezért minden bekapcsolás után add ki újra).

Ha megvan: `n36`.

---

## 4. szint – teljes szkennelés, a weboldalig

### 4.1 Előkészítés

- A korong (`capture/disc_a4.svg`, **100 %-os** nyomtatás, az 5 cm-es skála vonalzóval ellenőrizve) a tányéron, a tárgy a szaggatott kör közepén.
- **Tárgy:** matt és mintás, 10–25 cm-es (cipő, plüss, festett figura, fatárgy). **Mérd le a leghosszabb méretét.**
- **Egyszínű háttér** (fehér karton vagy fal), **egyenletes, szórt fény** kemény árnyék nélkül.
- **A telefon megtámasztva** 40–50 cm-re, kb. 20°-kal a tárgy fölött; a tárgy töltse ki a kép kb. felét.

### 4.2 Fotózás

1. **1. kör:** Serial Monitorban `s` → 36 megállás, **mindegyiknél egy fotó kézzel**. (Motor nélkül: kézzel forgatva 10°-os jelenként.)
2. Emeld a telefont kb. 45°-ra, **ugyanabban a tájolásban** (álló vagy fekvő), mint az első körben. **2. kör:** újabb 36 fotó.
3. A kezed ne legyen a képen, és a telefont az érintésen kívül ne mozdítsd. Egy-két kihagyott vagy dupla kép nem baj.

**Elvárt eredmény:** kb. 72 új, éles fotó a telefonon.

### 4.3 Átmásolás

USB → a telefonon „Fájlátvitel” → a `DCIM/OpenCamera` (vagy `DCIM/Camera`) mappából a 72 új képet másold ide: `~/Documents/cursor/Hackathon 2026/data/bejovo/`. Csak ennek a tárgynak a képeit.

### 4.4 Feldolgozás az ágenssel

```bash
cd "$HOME/Documents/cursor/Hackathon 2026"
.venv/bin/python agent/controller.py --inbox --size 0.24          # a lemért méret, méterben
```

**Elvárt kimenet (rövidítve):**
```
[vezérlő]   Indulás · modell_1 · …
[eszköz]    scan_info({})
[eredmény]  scan_info → {"images": 72, …}
[vezérlő]   Döntés: 72 fotó van, …
[eszköz]    reconstruct({"max_image_size": 2000})
[eredmény]  reconstruct → {"ok": true, "total_images": 72, "registered_images": 70, "sparse_models": 1, …}
…
[eszköz]    cleanup_model({"size_m": 0.24, "remove_disc": true})
[eredmény]  cleanup_model → {"ok": true, "disc_removed": true, "tilt_corrected_deg": 38.5, "object_size_cm": [6.2, 6.5, 1.0], …}
…
[eszköz]    quality_check({})
[eredmény]  quality_check → {"nev": "…", "minoseg": "jo", …}
[kész]      KÉSZ (N perc M s, K lépés)
```
- **Futásidő:** becslés szerint **8–20 perc** – ez lesz az első valódi mérés, írjátok fel. Közben a laptop legyen töltőn, a böngésző zárva.
- **Elvárt előnézet** (`data/modell_1/preview/view_0.png`): a tárgy **egyenesen áll**, felismerhető, a textúrája hasonlít a fotókhoz, oldalt nincs nagy lyuk. **A korong nincs rajta** (`remove_disc`), az `object_size_cm` nagyjából egyezik a tárgy vonalzóval mért méretével (±10%). **Normális:** hiányzó vagy lapos alj, enyhén hepehupás felület, apró korongfolt a talp szélén.
- **Csak a korong levágása, ágens nélkül** (pár mp): `./blender/run.sh cleanup data/modell_1/model/model.obj /tmp/k.glb --remove-disc` → `DISC: {"tilt_corrected_deg": …, "plane_noise_mm": 0.35, "cut_mm": 1.0, …, "object_size_cm": […]}`. Ha a tárgy alja is eltűnt: `--cut-mm 0.5`; ha korongmaradék látszik: `--cut-mm 2`.

### 4.5 Közzététel

Ha az eredmény jó, ugyanazon a mappán, közzététellel (a kész lépéseket az ágens nem ismétli meg feleslegesen):
```bash
.venv/bin/python agent/controller.py data/modell_1 --size 0.24 --publish
```
**Elvárt:** `publish_model → {"published": true, "pushed": true, "live": true, "url": "…/models/<név>.glb"}`, a GitHubon új `Add: <név>` commit.

### 4.6 Ellenőrzés a weboldalon

- **Helyben:** `cd web && python3 -m http.server 8000` → http://localhost:8000
- **Élesben:** https://r3dy-web.vercel.app (Ctrl+Shift+R-rel frissítve).

**Elvárt eredmény:**
- **Kártya** a quality_check által adott névvel, forgatható 3D modellel; a kiírt méret leghosszabb oldala egyezik a lemérttel.
- **Letöltés:** a GLB és a .blend működik; a GLB a Blenderben (File → Import → glTF) valódi méretű, a talpa az origóban.
- **Telefonon:** megjelenik az „AR” gomb, és a tárgy valódi méretben elhelyezhető a szobában.

---

## 4b. Videós változat

1. Serial Monitor: `c` (1 RPM), vagy kézzel, lassan és egyenletesen. Open Camera **videó** módban, zárolt fókusszal és expozícióval, stabilizálás **kikapcsolva**.
2. **1 kör (60 s)** alacsonyról, a felvétel megállítása nélkül emeld fel a telefont, még **1 kör** fölülről. Felvétel vége, majd `x`.
3. **Csak a videófájlt** másold a `data/bejovo/` mappába, és futtasd ugyanúgy (`--inbox`).

**Elvárt:** az ágens `extract_frames`-szel kezd (`"images": 150`), utána ugyanúgy folytatja. Futásidő: 10–25 perc. A modell általában valamivel gyengébb, mint fotókból.

---

## 5. szint – az önjavító kör (szándékosan rossz szkennelések)

Ez mutatja meg, hogy az ágens nem csak lefuttat egy szkriptet, hanem **észreveszi a hibát, és javít**. Minden esetben jegyezd fel a döntéseit (`data/modell_N/agent_log.jsonl`), és hogy jók voltak-e.

| # | hiba | hogyan idézd elő | elvárt reakció |
|---|---|---|---|
| 5.1 | zavaros háttér | a tárgy mögött rendetlen polc, könyvek | kevés regisztrált kép vagy háttér a modellen → `mask_background`, újra `reconstruct`, összevetés |
| 5.2 | kevés kép | csak 15 fotó | figyelmeztet a 20 alatti képszámra; ha nem áll össze, `failed` + fotózási tanács |
| 5.3 | hiányzó szög | csak egy kör, alacsonyról | a quality_check jelzi a hiányos tetejét; az összefoglaló plusz kört javasol felülről |
| 5.4 | elfordított telefon | kör közben álló → fekvő | több részmodell vagy dőlő modell → jelzi, más `up_axis`-szel próbálkozik |
| 5.5 | kevés videomemória | (szimuláció) `reconstruct` 2000 helyett is OOM-ot ad | `cuda_oom` → 1600, majd 1200 |

**A demóhoz** válasszátok ki azt az esetet, ahol a javítás a leglátványosabb (várhatóan 5.1), és ennek a képeit őrizzétek meg tartaléknak.

---

## Megfelelt / nem felelt meg

| # | feltétel | megfelelt |
|---|---|---|
| 1 | a mintán az ágens `KÉSZ`-szel zár, álló kastély | ☐ |
| 2 | a motor 10°-onként lép és megáll, 1 RPM-en 60 s egy kör | ☐ |
| 3 | a próbakörben 4 megállásnál 4 éles, kézzel exponált fotó | ☐ |
| 4 | 72 fotóból `KÉSZ`, a futásidő feljegyezve: ____ perc | ☐ |
| 5 | az előnézeten a tárgy áll és felismerhető, a quality_check „jo” | ☐ |
| 6 | a modell kint van az oldalon, helyes mérettel, forgatható | ☐ |
| 7 | a GLB letölthető, és a Blenderben valódi méretű | ☐ |
| 8 | legalább egy rossz szkennelést az ágens felismert és javított | ☐ |

Az 1., 4–6. és 8. pont az MVP. A mért futásidőt írjátok be a `TERV.md` 4. részébe.

## Ha valami nem sikerül

| mit látsz | ok | teendő |
|---|---|---|
| `[hiba] Érvénytelen vagy hiányzó ANTHROPIC_API_KEY` | nincs vagy rossz a kulcs | `.env`: `ANTHROPIC_API_KEY=sk-ant-…` |
| `[hiba] Nincs kapcsolat az API-val` | nincs internet | tartalék lánc: `./pipeline/auto.sh --size 0.24 --no-ai` |
| `reconstruct → "ok": false, "error_category": "registration_failed"` | a képek nem illeszthetők | egyszínű háttér, több fény, a korong mintája látsszon; az ágens maszkolással is próbálkozik |
| a modell egy kusza „felhő”, vagy rajta van a háttér | mintázott háttér | fehér háttér előtt újra, vagy hagyd, hogy az ágens maszkoljon |
| a modell ferde vagy fejjel lefelé áll | a telefon tájolása a körök között megváltozott | fotózd újra egy tájolásban |
| egy oldalon lyukas | onnan kevés kép készült | harmadik kör más magasságból |
| `publish_model → "pushed": false` | hálózati vagy git-hitelesítési gond | a commit helyben megvan, később `git push` |
| az ágens `finish` nélkül megáll / körbe jár | a lépés- vagy hívási korlát elfogyott | nézd meg az `agent_log.jsonl`-t; a döntési támpontok az `agent/controller.py` rendszerpromptjában |

A teljes eszköz-kimenet: `data/modell_N/agent_run.log`; az ágens döntései: `data/modell_N/agent_log.jsonl`.

**Ha egyáltalán nem áll össze:** a tárgy álljon egy helyben, és te sétálj körülötte, kb. 40 fotót készítve. Ha így működik, a forgóasztal vagy a háttér a gond, nem a szoftver.

## Takarítás a teszt után

- **Tesztmodell levétele az oldalról:** töröld a bejegyzését a `web/models/models.json`-ból, valamint a `web/models/<név>.glb` és `.blend` fájlt, majd `git commit -am "Remove test model" && git push`.
- **Helyi mappák:** a `data/modell_N` mappák törölhetők (a `data/` nincs a gitben).
