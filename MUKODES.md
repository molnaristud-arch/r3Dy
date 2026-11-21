# Működés – elmélet és gyakorlati megvalósítás

Ez a dokumentum azt írja le, **mi történik** a tárgy lefotózásától addig, hogy a 3D modell megjelenik a weboldalon, és azt is, **miért és hogyan** működik az egyes lépés. A tervezési döntéseket és az ütemtervet a [TERV.md](TERV.md), a tesztelést a [TESZT.md](TESZT.md) tartalmazza.

**Tartalom**
1. [Áttekintés](#1-áttekintés)
2. [Elmélet](#2-elmélet) – hogyan lesz fényképekből 3D modell
3. [Gyakorlati megvalósítás](#3-gyakorlati-megvalósítás) – a lánc lépésről lépésre, fájlokkal és parancsokkal
4. [Számok, korlátok, továbblépés](#4-számok-korlátok-továbblépés)

---

## 1. Áttekintés

A cél: **egy valódi tárgyról néhány perc alatt textúrázott, valódi méretű 3D modell**, amely egy nyilvános weboldalon megtekinthető (forgatható, AR-ben a szobába helyezhető) és letölthető (GLB, .blend).

A módszer **fotogrammetria**: a tárgyról sok, átfedő fénykép készül különböző irányokból; a képeken megtalált közös pontokból a program kiszámolja, honnan készült az egyes kép, majd ebből a tárgy térbeli alakját és felületi mintázatát. A modellt nem „kitalálja” egy AI, hanem **a fotókból méri**: ezért hű a valódi tárgyhoz.

```
 FELVÉTEL                    FELDOLGOZÁS (laptop, GPU)                             KÖZZÉTÉTEL
┌──────────────────┐   ┌─────────────────────────────────────────────────────┐   ┌──────────────────┐
│ forgóasztal      │   │ 0. képek átvétele (fotó / videó → legélesebb kockák)│   │ publish.py       │
│ (kézi / Arduino) │   │ 1. jellemzőpontok (SIFT)              ┐             │   │ models.json + GLB│
│ + nyomtatott     │──►│ 2. párosítás                          │ COLMAP      │──►│ git push         │
│   korong         │USB│ 3. kamerapozíciók (SfM) + igazítás    ┘             │   │ Vercel élesít    │
│ + telefon        │   │ 4. torzításmentesítés                               │   │ model-viewer     │
│   (Open Camera)  │   │ 5. sűrű pontfelhő                     ┐             │   │ (3D, AR, letölt.)│
└──────────────────┘   │ 6. háló                               │ OpenMVS     │   └──────────────────┘
                       │ 7. textúra                            ┘             │
                       │ 8. tisztítás, méretezés, GLB          ─ Blender     │
                       │ 9. előnézeti képek                    ─ Blender     │
                       └─────────────────────────────────────────────────────┘
                         mindezt a vezérlő ágens (agent/controller.py, Claude) vezérli:
                         minden lépés után ő dönt a folytatásról (tartalék: pipeline/auto.sh)
```

---

## 2. Elmélet

### 2.1 A kamera mint vetítés

Egy fénykép a térbeli világ **vetülete** egy síkra. A telefon kamerája jó közelítéssel **lyukkamera (pinhole)**: minden térbeli X pont a kamera középpontján át egyenes vonalban a képsíkra vetül:

```
  x  =  K · [R | t] · X
  │     │    │   │    └─ térbeli pont (X, Y, Z, 1)
  │     │    └───┴────── külső paraméterek: a kamera helyzete (R forgatás, t eltolás) – képenként más
  │     └─────────────── belső paraméterek: fókusztávolság, képközéppont (+ lencsetorzítás) – a telefonra jellemző
  └───────────────────── pixel a képen
```

A vetítés során a **mélység elveszik**: egy pixelhez a térben egy egész sugár tartozik. Ha viszont ugyanazt a pontot **két különböző helyről** is látjuk, a két sugár metszéspontja kijelöli a pont térbeli helyét – ez a **háromszögelés (trianguláció)**, ugyanaz az elv, amivel a két szemünk mélységet érzékel. Sok kép, sok pont esetén a kamerák helyzete és a pontok helye együtt kiszámolható – ez a fotogrammetria lényege.

### 2.2 Jellemzőpontok (SIFT)

Ahhoz, hogy két képen ugyanazt a pontot megtaláljuk, a program **jellemzőpontokat** keres: olyan helyeket, amelyek jól azonosíthatók (sarkok, foltok, mintázat-részletek). A COLMAP a **SIFT** eljárást használja (GPU-n):

- a képet több méretben elemzi, és azokat a pontokat tartja meg, amelyek méretváltozásra és elforgatásra is stabilak;
- minden ponthoz egy 128 számból álló **leírót** számol (a környező kis terület élirányainak eloszlása), ami nagyjából független a fényerőtől és a nézőponttól.

Egy jó fotón több ezer jellemzőpont van. **Ezért kell a tárgynak mintázottnak lennie:** egy egyszínű, sima felületen nincs mit megtalálni, egy fényes felületen pedig a tükröződés nézőpontonként máshol van, így „hamis” pontokat ad.

### 2.3 Párosítás és geometriai ellenőrzés

A program **minden képpárt** összevet (*exhaustive matching*): a leírók alapján megkeresi, melyik pont melyiknek felel meg. A leíró-alapú párosításban sok a hibás pár, ezért jön a **geometriai ellenőrzés**: két kép valódi pontpárjainak egy közös geometriai szabálynak (epipoláris geometria – az *alapmátrix* vagy *esszenciális mátrix*) kell megfelelniük. A **RANSAC** eljárás véletlen kis mintákból újra és újra megbecsüli ezt a szabályt, és azt tartja meg, amelyikkel a legtöbb pár egyezik; a többi párt eldobja.

A minden-mindennel párosítás a képszám **négyzetével** nő (72 képnél ~2 600 pár, 150-nél ~11 000), de ennyi képnél a GPU-n még gyors, és a legmegbízhatóbb.

### 2.4 Kamerapozíciók: Structure from Motion (SfM)

A COLMAP **inkrementális** SfM-et futtat (*mapper*):

1. választ egy jól párosított **kezdő képpárt**, és ebből háromszögeli az első térbeli pontokat;
2. sorra **hozzáveszi a további képeket**: a már ismert térbeli pontok és a kép pontjai közti megfelelésekből kiszámolja az új kép helyzetét (*PnP – Perspective-n-Point*);
3. az új kép segítségével **újabb pontokat** háromszögel;
4. időnként **kötegelt kiegyenlítést** (*bundle adjustment*) futtat: az összes kamerahelyzetet, a kamera belső paramétereit és az összes pontot egyszerre finomítja úgy, hogy a pontok visszavetítési hibája (hol kellene látszania a pontnak a képen, és hol látszik valójában) minimális legyen.

Az eredmény: **minden kép helye és iránya**, a telefon kamerájának paraméterei (a program becsüli – ezért elég, hogy minden kép ugyanazzal a telefonnal, ugyanazzal a beállítással készül: `single_camera`), és egy **ritka pontfelhő** (néhány tízezer pont).

**A mérték ismeretlen.** Képekből csak arányok számolhatók: egy kétszer akkora tárgy kétszer olyan messziről pontosan ugyanígy néz ki. A modell valódi méretét ezért utólag kell megadni (2.10).

### 2.5 A forgóasztal-trükk

A fotogrammetria klasszikusan úgy működik, hogy **a kamera mozog** egy álló tárgy körül. Mi fordítva csináljuk: **a kamera áll, a tárgy forog**. Matematikailag ez egyenértékű – a kamera a tárgyhoz képest ugyanúgy körbejár –, **de csak akkor, ha a képen minden együtt forog a tárggyal.**

- Ha a háttérben mintázott, **álló** dolog látszik (könyvespolc, poszter), a program arra is talál pontokat, azok viszont azt mondják, hogy a kamera *nem mozdult*. A kétféle „igazság” összezavarja: hibás lesz a pozícióbecslés, vagy szét sem tudja választani a képeket. **Ezért kell egyszínű háttér.**
- A **nyomtatott korong** a tárggyal együtt forog, és sűrű, véletlen fekete-szürke mintázata **rengeteg jellemzőpontot** ad akkor is, ha maga a tárgy kevéssé mintázott. Ez stabilizálja a pozícióbecslést.
- Ha mégis zavaros a háttér, a `--mask` kapcsoló minden képről kivágja a hátteret (`rembg` neurális háló, u2net modell), és fehérre cseréli. Ilyenkor a korong is eltűnik, így a pozícióbecslés csak a tárgy saját mintázatára támaszkodik.

A korong **fokbeosztása** (10°-onként) a kézi forgatáshoz kell: ehhez képest látszik, mennyit kell fordítani. A program nem igényel pontos szögeket – a 2.4-es lépés minden kép helyzetét magától kiszámolja.

### 2.6 Függőleges igazítás

Az SfM koordináta-rendszere **önkényes**: a modell bármilyen irányban állhat (az első próbán fejjel lefelé állt). Az igazítás (`model_orientation_aligner --method IMAGE-ORIENTATION`) azt használja ki, hogy a fotókat **egyenesen tartott telefonnal** készítjük: a képek „fel” iránya átlagosan a valódi függőleges. Ebből a program megbecsüli a gravitáció irányát, és a modellt úgy forgatja, hogy az a COLMAP kamerakonvenciója szerinti **+Y** tengely legyen (a Blender-importnál ezért `up = -Y`).

**Ezért nem szabad** a körök között a telefont álló és fekvő helyzet között váltogatni – vagy legalábbis minden képen ugyanaz legyen a „fel”.

### 2.7 Torzításmentesítés

A telefon lencséje kissé torzít (a képszéli egyenesek görbülnek). A becsült torzítási paraméterekből a program **kiegyenesített** képeket készít (`image_undistorter`), mert a következő lépések ideális lyukkamerát feltételeznek. Itt kicsinyít is: a hosszabbik oldal legfeljebb **2000 pixel**, hogy a 6 GB-os videokártya memóriájába beférjen.

### 2.8 Sűrű pontfelhő: Multi-View Stereo (MVS)

Az SfM pontfelhője ritka – csak a jellemzőpontok. Most **minden pixelnek** keresünk mélységet. Az OpenMVS (`DensifyPointCloud`) képenként **mélységtérképet** számol a *PatchMatch* eljárással:

- minden pixelhez véletlenszerű mélység- és felületirány-tippet rendel;
- egy tipp jóságát úgy méri, hogy a pixel kis környezetét a tipp szerint átvetíti a szomszédos képekre, és megnézi, mennyire **hasonlít** ott a kép (normalizált keresztkorreláció – *photo-consistency*);
- a jó tippeket továbbadja a szomszédos pixeleknek (a felületek folytonosak), és véletlen módosításokkal finomít – néhány kör alatt összeáll a mélységtérkép;
- végül a mélységtérképeket **összeolvasztja**: csak azokat a pontokat tartja meg, amelyeket több kép is megerősít.

Az eredmény egy **sűrű pontfelhő** (százezres–milliós nagyságrend), színekkel.

### 2.9 Háló (mesh)

Pontfelhőből még nem lesz tárgy: kell egy összefüggő **felület**. Az OpenMVS (`ReconstructMesh`) a pontokból **Delaunay-tetraéderhálót** épít (a teret pontok közti tetraéderekre bontja), majd minden tetraéderről eldönti, hogy a tárgy **belsejében** vagy **kívül** van-e. Ebben a láthatóság segít: ami egy kamera és egy általa látott pont között van, az biztosan üres tér. A döntést egy **gráfvágás** (minimális vágás) hozza meg globálisan; a belső és külső tetraéderek határa adja a felületet – háromszöghálót, néhány százezer háromszöggel.

Ahová egyetlen kamera sem látott – **a tárgy alja**, amin áll –, ott a programnak nincs adata: ez a rész hiányzik vagy lapos.

### 2.10 Textúra

A háló színét a fotókból kapja (`TextureMesh`):

1. **nézetválasztás:** minden háromszöghöz kiválasztja, melyik fotó látja a legjobban (közelről, merőlegesen, élesen), úgy, hogy a szomszédos háromszögek lehetőleg ugyanabból a képből kapjanak színt (kevesebb varrat) – ez is egy globális optimalizálás;
2. az összetartozó darabokat **textúra-atlaszba** (egy vagy néhány, legfeljebb 4096×4096-os képbe) csomagolja, és minden háromszöghöz feljegyzi, az atlasz melyik részét kell rá „ragasztani” (UV-koordináták).

Az OpenMVS a különböző fotókból jövő darabok színkülönbségét **varratkiegyenlítéssel** (*seam leveling*) simítaná, de a 2.4-es verzióban ez sötét foltokkal teli atlaszt adott – ezért **kikapcsoltuk** (tesztelve: így a színek a fotókéval egyeznek).

### 2.11 Tisztítás, méretezés, formátum (Blender)

A nyers modell három okból nem használható közvetlenül: túl sok háromszögből áll (több MB, lassú a böngészőben), körülötte lebegő törmelék van, és **a mérete önkényes**. A Blender (fej nélküli, parancssori módban) ezt javítja:

| lépés | elv |
|---|---|
| **legnagyobb darab megtartása** | a hálót összefüggő részekre bontja, és csak a legnagyobbat tartja – a zaj kis, különálló darabokban marad le |
| **egyszerűsítés** 50 000 háromszögre | élösszevonásos decimálás: azokat az éleket vonja össze, amelyek elhagyása a legkevésbé változtat az alakon; a textúra miatt a látvány alig romlik |
| **méretezés** | a leghosszabb kiterjedést a megadott valódi méretre (`--size`, méterben) skálázza – ez pótolja az SfM ismeretlen mértékét (2.4) |
| **talppont** | a tárgy alját a talajsíkra, közepét az origóba teszi: így bármilyen programba vagy AR-be importálva „a földön áll” |
| **simított árnyalás** | a háromszögek határai nem látszanak élként |
| **export** | **GLB** (+ szerkeszthető `.blend`) |

**A GLB** a glTF 2.0 („a 3D JPEG-je”) bináris változata: egyetlen fájlban a háló, a textúra képe és az anyagleírás. Méterben, Y-felfelé koordinátákkal dolgozik – ezt használja minden webes megjelenítő, a Blender, a Unity, az Unreal, és az AR-nézők.

### 2.12 Megjelenítés a weben

A weboldal a Google **`<model-viewer>`** komponensét használja: egy HTML-elem, amely a GLB-t **WebGL**-lel, a böngészőben rendereli (a videokártyán): egérrel/ujjal forgatható, nagyítható, magától lassan forog. Az `ar` attribútum miatt telefonon megjelenik az **AR** gomb: Androidon a Scene Viewer / WebXR, iPhone-on a Quick Look a kamera képébe helyezi a tárgyat – **valódi méretben**, ezért fontos a 2.11-es méretezés.

### 2.13 Videós felvétel: miért kell lassan forgatni

Videónál a tárgy **expozíció közben is mozog**. A bemozdulás (pixelben) = a felület sebessége × záridő × felbontás. Egy 10 cm sugarú tárgy szélének sebessége 1 fordulat/percnél ~1 cm/s; szobai fényben (~1/60 s záridő) ez **< 1 pixel** – éles. 300 fordulat/percnél (PC-ventilátor) 3 m/s, ami 1/1000 s-nál is ~15 pixel, ráadásul a telefon szenzora soronként olvas ki (*rolling shutter*, 10–30 ms), így a tárgy egy képkockán belül is 18–54°-ot fordul el – torz, használhatatlan.

A videóból a program **egyenletes időablakokra** bontva ablakonként a **legélesebb** képkockát tartja meg. Az élesség mértéke a **Laplace-szűrt kép szórása**: a Laplace-operátor az éleket emeli ki, egy éles képen sok az erős él (nagy szórás), egy elmosódotton kevés.

### 2.14 Motoros forgatás: léptetőmotor

A **28BYJ-48** léptetőmotor tekercseit meghatározott sorrendben kapcsolgatva a tengely apró, pontos lépésekben fordul. Félléptetéses üzemben a motor 64 lépést tesz egy fordulatra, a beépített **1 : 63,68 áttétel** után a kimenő tengely **≈ 4076 lépés/fordulat** – így 10° ≈ 113 lépés, ~0,09° pontossággal. Az áttétel miatt áram nélkül is megtartja a helyzetét, és erős, de lassú (max. ~10–15 fordulat/perc) – pont amilyen egy forgóasztalhoz kell.

A telefont **kézzel exponáljuk**: a motor minden 10°-os lépés után megáll, és amíg áll, valaki elkészíti a fotót. A soros monitor `FOTO k/36` sora jelzi a megállást. Így a telefon felé nem kell semmilyen kábel vagy elektronika. (A vázlat megálláskor a D7-re egy sípszót is kiad – egy oda kötött zümmerrel az Open Camera hangvezérlése automatikusan exponálhatna –, de ezt nem használjuk; zümmer nélkül ennek nincs hatása.)

---

## 3. Gyakorlati megvalósítás

### 3.1 Hardver és környezet

| elem | konkrétan |
|---|---|
| feldolgozó gép | MSI GP65: i7-10750H, 16 GB RAM, **RTX 2060 6 GB** (CUDA), Ubuntu 26.04 |
| telefon | Android (**Open Camera**) vagy iPhone (beépített Kamera, AE/AF-zárral) – fókusz és expozíció zárolva, **kézi exponálás** minden megállásnál |
| forgóasztal | **Arduino Nano + ULN2003 + 28BYJ-48 (5 V) léptetőmotor**, 10°-os lépésekkel; a tányéron a nyomtatott korong (`capture/disc_a4.svg`) |
| COLMAP 4.2.1, OpenMVS 2.4.0 | **CUDA-s** változat, a micromamba `scan` környezetben (az Ubuntu `colmap` csomagja hibás, és GPU nélküli) |
| Blender 5.0.1 | parancssorból (`-b`), a projekt `.venv`-jéből kölcsönzött numpy-val (a glTF-exporthoz kell) |
| Python `.venv` | OpenCV (videó, élesség), rembg + onnxruntime (háttérkivágás GPU-n) |
| weboldal | statikus HTML + `<model-viewer>@4.0.0`, **Vercel**, a GitHub-repó `web/` mappájából |

Telepítés és ellenőrzés: `./setup.sh` (idempotens – hiányzó elemnél kiírja a telepítő parancsot, a meglévőket csak ellenőrzi).

### 3.2 Felvétel

**Motoros léptetés, kézi exponálás (a használt mód):** a telefon rögzítve (állvány, tartó vagy könyvkupac), ~40–50 cm-re; az Arduino 10°-onként forgat és megáll, mi minden megállásnál exponálunk → 36 kép/kör; két kör (≈20° és ≈45° magasságból) → **~72 kép**. Ha egy-két kép kimarad vagy duplán készül, nem baj: a szoftver a képekből számolja a helyzetüket, nem a darabszámból. Motor nélkül ugyanez kézi forgatással is megy. Az Open Camerában a fókusz, az expozíció és a fehéregyensúly **zárolva**: így minden képen ugyanolyan a tárgy színe és élessége, ami a párosításnak (2.3) és a textúrának (2.10) is kell.

**Arduino-léptetés:** `capture/turntable_stepper/turntable_stepper.ino`. Egy *állapotgép* fut a `loop()`-ban, megakadás nélkül (a gomb és a soros parancsok bármikor hatnak):

```
IDLE ──s/gomb──► SETTLE (0,6 s várakozás) ──► „FOTO k/36” → itt exponálunk ──► DWELL (2,5 s áll, d-vel állítható)
                    ▲                                                     │
                    └──── MOVE: 10° (lassú indulás és fékezés, ~0,3 s) ◄──┘   36 után ─► IDLE
IDLE ──c──► CONT: folyamatos forgás, lépésköz = 60 s / (RPM × 4076)
```

- A megállási pozíciókat **kumulatívan** számolja (k-adik megálló = round(k × 4076 / 36)), így a kerekítési hibák nem adódnak össze (szimulációban: 9,98–10,07° lépések).
- Állás közben **lekapcsolja a tekercseket** (nem melegszik; az áttétel megtartja a tányért).
- Tesztelés hardver nélkül: `capture/stepper_sim/run.sh` – a vázlatot a PC-n fordítja egy Arduino-utánzattal, és szimulált idővel végigjátssza.

**Videó (B mód):** a tányér folyamatosan, **~1 fordulat/perc** sebességgel forog (kézzel vagy `c` paranccsal), egy videóban két kör két magasságból.

### 3.3 A lánc vezérlése: a vezérlő ágens (`agent/controller.py`)

```bash
.venv/bin/python agent/controller.py --inbox --size 0.24          # data/bejovo/ → data/modell_N
.venv/bin/python agent/controller.py data/modell_1 --publish       # meglévő szkennelés, feltöltéssel
```

A láncot nem egy fix sorrendű szkript futtatja, hanem egy **AI ágens** (Claude Opus 5.5, eszközhívással). A lánc lépései (3.4–3.8) az **eszközei**; minden lépés után megkapja az eredményt, és **ő dönti el**, mi jöjjön:

```
            ┌────────────── Claude (vezérlő) ──────────────┐
            │ „Döntés: 71/96 kép regisztrálódott, a háttér │
            │  zavarhat → háttérkivágás, majd újra.”       │
            └──────┬───────────────────────────▲───────────┘
          eszközhívás                    eredmény (JSON + képek)
                   ▼                           │
 scan_info · extract_frames · mask_background · remove_mask · reconstruct
 cleanup_model · render_preview · quality_check · publish_model · finish
```

- **Eszközök** (`agent/tools.py`): vékony burkolók a meglévő szkriptek körül. Mindegyik **egyetlen, induláskor rögzített** szkennelés-mappán dolgozik (az ágens nem adhat meg tetszőleges útvonalat), rövid, gépileg olvasható eredményt ad, a teljes kimenet a `modell_N/agent_run.log`-ba kerül.
- **Jelek, amelyekből dönt:** a `reconstruct` visszaadja a **regisztrált képek arányát** (COLMAP `model_analyzer`), a **részmodellek számát** (1-nél több = a felvételi körök nem illeszkedtek) és a **hibakategóriát** (`cuda_oom`, `registration_failed`, `timeout`); a `render_preview` az előnézeteket és egy eredeti fotót **képként** adja át, így az ágens látja is a modellt; a `quality_check` egy független második véleményt ad (3.8).
- **Tipikus döntések:** kevés regisztrált kép + zavaros háttér → `mask_background`, majd újra; `cuda_oom` → kisebb képméret (1600, 1200); dőlő modell → más `up_axis` a tisztításnál; „gyanús” ítélet → javítás és újraellenőrzés.
- **Korlátok:** a lassú lépések hívásszáma korlátos (pl. `reconstruct` legfeljebb 4×), összesen legfeljebb 30 lépés; ha elfogynak a lehetőségek, az ágens `failed` státusszal zár, és leírja, mit kell másképp fotózni.
- **Biztonság:** `--publish` nélkül semmit nem tölt fel; az AGPL-es tesztkészletből (`data/sample`) készült modell közzétételét az eszköz maga tiltja (a képek md5-je alapján).
- **Napló a demóhoz:** minden döntés („Döntés: …”), gondolat-összefoglaló, eszközhívás és eredmény a terminálra **és** a `modell_N/agent_log.jsonl`-be kerül (soronként egy JSON-esemény).

**Tartalék lánc – `pipeline/auto.sh`:** ugyanezeket a lépéseket fix sorrendben futtatja, ágens nélkül (`./pipeline/auto.sh --watch --size 0.24`). Figyeli a `data/bejovo/` mappát, megvárja a másolás végét (a mappa ujjlenyomata `--settle` másodpercig nem változik), új `data/modell_N`-t nyit, lefuttatja a láncot, a végén a minőségellenőrző ágenstől kér javaslatot, és rákérdez a feltöltésre. Kapcsolók: `--size`, `--frames`, `--mask`, `--max`, `--no-open`, `--no-publish`, `--no-ai`, `--help`.

### 3.4 Videóból képek: `pipeline/extract_frames.py`

Ha van videó: a videót `--frames` (150) egyenlő **időablakra** osztja, ablakonként a legnagyobb **Laplace-szórású** (2.13) kockát írja ki JPEG-be (hosszabbik oldal ≤ 2400 px). Több videónál a kockaszám eloszlik, a fájlnevek előtagot kapnak (`video1_…`, `video2_…`).

- Kockánként csak a **folyó ablak legjobbját** tartja memóriában (4K videónál 0,5 GB, ~33 s egy perces videóra; a korábbi változat 4,2 GB-ot evett).
- Az élességet fél felbontáson méri (négyszer gyorsabb, ugyanazt a sorrendet adja).
- Az álló helyzetben felvett telefonvideók forgatási metaadatát az OpenCV alkalmazza – a kockák is állók (tesztelve).

### 3.5 Rekonstrukció: `pipeline/reconstruct.sh`

Bemenet: `modell_N/images` (vagy `--mask` esetén `modell_N/masked`). Munkamappa: `modell_N/work` (minden futáskor újra készül).

| # | parancs | elmélet | kimenet |
|---|---|---|---|
| 1/7 | `colmap feature_extractor --ImageReader.single_camera 1 --FeatureExtraction.max_image_size 2000` | 2.2 – SIFT, GPU | `work/db.db` |
| 2/7 | `colmap exhaustive_matcher` | 2.3 – párosítás + RANSAC | `db.db` |
| 3/7 | `colmap mapper`, majd `model_orientation_aligner --method IMAGE-ORIENTATION` | 2.4, 2.6 – SfM, függőleges | `work/sparse/0`, `work/aligned` |
| 4/7 | `colmap image_undistorter --max_image_size 2000` | 2.7 | `work/dense` |
| 5/7 | `InterfaceCOLMAP` → `DensifyPointCloud --resolution-level 1` | 2.8 – PatchMatch MVS | `scene_dense.mvs` |
| 6/7 | `ReconstructMesh` | 2.9 – Delaunay + gráfvágás | `scene_dense_mesh.ply` |
| 7/7 | `TextureMesh --max-texture-size 4096 --global-seam-leveling 0 --local-seam-leveling 0 --export-type obj` | 2.10 | **`model/model.obj`** + textúra |

Ha a 3. lépés nem tud modellt építeni (kevés átfedés vagy mintázat), a szkript itt **hibával megáll** – ez a leggyakoribb hiba, és mindig a felvételen kell javítani.

### 3.6 Utómunka: `blender/run.sh cleanup` (`blender/cleanup.py`)

```bash
./blender/run.sh cleanup modell_N/model/model.obj modell_N/model.glb --size 0.24 --blend
```

Pontosan a 2.11-es lépések: OBJ-import (`up = -Y`), legnagyobb darab, decimálás 50 000 háromszögre, méretezés, talppont az origóban, simítás, **GLB + .blend**. A `run.sh` a Blendert fej nélkül indítja, a `.venv` numpy-jával, és a Python-hibát **nem nulla kilépési kóddal** jelzi – enélkül a Blender hiba esetén is „sikert” jelentene, és a lánc hibás modellel menne tovább.

**Korong levágása (`--remove-disc`, forgóasztalos szkennelésnél ajánlott):**

```bash
./blender/run.sh cleanup modell_N/model/model.obj modell_N/model.glb --remove-disc --disc-diameter 0.19
```

1. **Síkkeresés (RANSAC):** a háló legfeljebb 150 000 pontjából 500-szor három véletlen pontra síkot illeszt; az a sík nyer, amelyhez a legtöbb pont van 0,4%-on (a befoglaló átló arányában) belül – ez a korong. 8% alatti támogatottságnál hiba (nincs korong a modellen).
2. **Finomítás:** a síkhoz tartozó pontokra legkisebb négyzetes sík (a 3×3-as kovariancia legkisebb sajátvektora); a normál a tárgy felé mutat.
3. **Vízszintezés:** forgatás, amely a normált a +Z-be viszi (Rodrigues) – így a COLMAP-igazítás dőlését is javítja (mért: 38,5° és 92,1°).
4. **Méretezés a korongból:** a korongpontok sugara (98. percentilis) a nyomtatott korong ismert átmérőjének fele → **valódi méret mérés nélkül** (a `--size` ilyenkor nem számít).
5. **Levágás:** törlődik minden csúcs a sík fölötti `--cut-mm` (alap 1 mm, de legalább a síkzaj 3σ-ja) alatt és a korong sugarán kívül; utána a legnagyobb darab marad.

A kimenet `DISC: {…}` sora: `tilt_corrected_deg`, `disc_support`, `plane_noise_mm`, `cut_mm`, `object_size_cm`. Mért (Arduino Uno, 19 cm-es korong): 6,2 × 6,5 × 1,0 cm (38 kép) és 6,3 × 7,8 × 1,2 cm (76 kép), 3–5 s, 0,6–1,2 GB memória. A 2 mm-es vágás már lyukakat ütött a lapos panelbe, ezért lett 1 mm az alap.

**Memória:** a `run.sh` a Blendert `systemd-run --user --scope -p MemoryMax=6G` alatt indítja (`BLENDER_MEM` env), így túlfutáskor csak a Blender áll le, nem a terminál. A darabokra bontás scipy-összefüggőkomponensekkel és egyetlen kijelölés + törlés megy (a Blender `separate(LOOSE)` a korong levágása után több ezer objektumot hozna létre).

### 3.7 Előnézet: `blender/run.sh preview` (`blender/preview.py`)

Négy nézet (elölről, kissé felülről, majd 90°-onként körbe) 800×800-as, átlátszó hátterű PNG-be (`modell_N/preview/view_0..3.png`), a Blender gyors *Workbench* renderelőjével, textúraszínekkel és stúdiófénnyel. Ez a **minőségellenőrzés**: a `view_0.png`-n a tárgynak állnia kell, felismerhetőnek lennie.

### 3.8 Minőségellenőrző és kurátor ágens (`agent/qa.py`)

Egy **második, független** Claude-ügynök (Claude Sonnet 5.5): a vezérlő a `quality_check` eszközzel hívja, a tartalék lánc (`auto.sh`) parancssorból.

```
qa.py ──► Claude Sonnet 5.5
  4 előnézet (512 px PNG, világosszürke háttérre)   │ JSON-séma (structured output):
  + 1 eredeti fotó (768 px JPEG)                    │ nev, leiras, cimkek, minoseg (jo|gyanus|hibas),
  + a modell mérete (cm, a GLB-ből)                 ▼ hibak, javaslat
                                                  vágás, tisztítás → JSON (+ model, size_cm)
```

- **Multimodális:** a képeket és az utasítást egy kérésben kapja; az utasítás elmondja, hogy az első képek a modell nézetei, az utolsó egy valódi fotó – az **összevetésből** ítéli meg, ép-e a modell (szétesett, torz, rajta maradt háttér, dől), és hogy a hiányzó alj és a talp alatti korongdarab normális.
- **Kötött kimenet:** `output_config.format` JSON-sémával, így a válasz garantáltan a várt mezőkkel érkezik; a kód még vágja és tisztítja (hosszkorlátok, egyszavas, kisbetűs címkék).
- **Miért külön ágens?** A vezérlő a saját munkáját ítélné meg; egy külön hívás, más modellel és csak a végeredményt látva, **független** második vélemény. A vezérlő a „gyanús/hibás” ítélet és a `javaslat` alapján javít, majd újra ellenőriztet.
- **Kurátor:** ugyanez a hívás írja meg a weboldal nevét, leírását és címkéit.
- **Hibatűrés:** ha az API nem érhető el, az `auto.sh` **kézi kérdésekre vált**; a vezérlő hibaként kapja vissza, és dönthet a folytatásról.

A tartalék láncban a javaslat így jelenik meg:

```
── AI-javaslat (claude-sonnet-5-5) ──
Név:      Fehér sportcipő
Leírás:   Fehér, bőr hatású sportcipő szürke talppal és fűzővel.
Címkék:   cipő ruházat
Méret:    10.4 × 28.0 × 11.2 cm
Minőség:  JÓ
Feltöltsem így? [I/n, s = szerkesztés]
```

- **Enter** → feltöltés a javaslattal; **n** → nem tölti fel; **s** → szerkesztés: méret (újra-tisztítással), majd a név, a címkék és a leírás **előre kitöltve**.
- **HIBÁS** ítéletnél az alapválasz a „nem”: érdemes újrafotózni.
- Ha nincs AI (`--no-ai`, nincs kulcs a `.env`-ben, nem érhető el): kézi kérdések jönnek.

Ezután:

- `publish.py` a GLB-t (és a `.blend`-et) a `web/models/<slug>.glb`-be másolja, a GLB **JSON-fejlécéből** kiolvassa a háromszögszámot és a befoglaló méretet, és felveszi a `web/models/models.json`-ba:
  ```json
  { "name": "Fehér sportcipő", "file": "feher-sportcipo.glb", "tags": ["cipő", "ruházat"], "faces": 50000,
    "size": "10.4 × 28.0 × 11.2 cm (sz × m × mag)",
    "description": "Fehér, bőr hatású sportcipő szürke talppal és fűzővel.", "blend": "feher-sportcipo.blend" }
  ```
- `git commit -- web/models` (csak a modellek, semmi más) és `git push` a GitHubra;
- ha a `SITE` környezeti változó be van állítva (az élő oldal címe), a szkript 5 másodpercenként lekéri az élő `models.json`-t, és megvárja, amíg a modell megjelenik (max. 3 perc) → `ÉLES: …`.

### 3.9 Weboldal és élesítés

- **GitHub** (privát repó): a teljes projekt. A `data/` (fotók, köztes fájlok) **nincs** benne (`.gitignore`) – túl nagy, és nem kell; a `.env` (API-kulcs) sincs.
- **Vercel** (https://r3dy-web.vercel.app): minden `main`-re érkező push után **automatikusan élesít**, ~20 másodperc alatt. Csak a **`web/` mappa** megy ki (Root Directory), így a kód, a terv és a dokumentáció nem nyilvános.
- **`web/index.html`**: betölti a `models.json`-t, és minden modellhez kártyát rajzol: `<model-viewer>` (forgatható, automatikusan forgó, AR, lusta betöltés), név, méret, háromszögszám, leírás, címkék, **GLB és .blend letöltés**, keresés név/leírás/címke szerint, világos/sötét téma (a rendszer beállítását követi). Külön szerver vagy adatbázis nincs: a „háttérrendszer” maga a git-repó.

### 3.10 Mappák egy feldolgozás után

```
data/
├── bejovo/                ← ide másolsz; a szkript kiüríti
└── modell_1/
    ├── images/            fotók vagy a videó legélesebb kockái
    ├── video/             (videós felvételnél) az eredeti videó
    ├── masked/            (--mask esetén) háttér nélküli képek
    ├── work/              COLMAP adatbázis, ritka modell, sűrű pontfelhő, háló – köztes fájlok
    ├── model/             model.obj + textúra (nyers, méretezetlen)
    ├── model.glb          ← a kész, tisztított, valódi méretű modell
    ├── model.blend        ← ugyanez Blender-fájlként
    ├── preview/           view_0..3.png
    ├── qa.json            a minőségellenőrző ágens utolsó ítélete
    ├── agent_log.jsonl    a vezérlő ágens döntései (eseménynapló)
    ├── agent_run.log      az eszközök teljes kimenete (ágens-futásnál)
    └── run.log            a teljes futás naplója (auto.sh-futásnál)
web/models/
├── models.json            a weboldal katalógusa
├── <slug>.glb, <slug>.blend
```

---

## 4. Számok, korlátok, továbblépés

### 4.1 Mért és becsült idők

| lépés | 11 kép (minta, mért) | 72 kép (becslés) |
|---|---|---|
| COLMAP (1–4/7) | ~11 s | 1–4 perc |
| sűrű pontfelhő (5/7) | ~11 s | 3–8 perc |
| háló (6/7) | ~19 s | 2–5 perc |
| textúra (7/7) | ~20 s | 1–3 perc |
| Blender + előnézet | ~6 s | ~10 s |
| **összesen** | **~1 perc 10 s** | **~8–20 perc** |
| videó → 150 kocka (4K, 1 perc) | ~33 s (mért) | |
| motoros kör, 36 fotó | ~2 perc (szimulált) | |

### 4.2 Korlátok – és mi okozza őket

| korlát | oka (melyik elméleti lépés) |
|---|---|
| fényes, átlátszó, tükröző tárgy nem megy | a tükröződés nézőpontonként vándorol → hamis jellemzőpontok, hibás photo-consistency (2.2, 2.8) |
| egyszínű, mintázatlan felület lyukas / hepehupás | nincs mit párosítani (2.2, 2.8) |
| a tárgy alja hiányzik | alulról egy kamera sem látta (2.9) – megoldás: megfordítva is lefotózni, két modell összeillesztése (nincs automatizálva) |
| mintázott háttér elrontja | a forgóasztal-trükk feltétele sérül (2.5) – egyszínű háttér vagy `--mask` |
| a méret a korongon múlik | az SfM mértéke ismeretlen (2.4); `--remove-disc` a korong ismert átmérőjéből méretez (3.6) – ha a korong nem látszik eléggé, kézi `--size` kell |
| vékony részek (drót, haj) eltűnnek | a 2000 px-es képméret és a háló felbontása nem bírja; a decimálás (2.11) tovább egyszerűsít |
| motor csak könnyű tárgyhoz | a 28BYJ-48 tengelye nem csapágy – nehezebb tárgynál a tányér súlyát csapágy (pl. áram nélküli ventilátor) vigye |

### 4.3 Továbblépési lehetőségek

- **Fotózási segítő ágens** (TERV 6.3): a beérkező képek ellenőrzése fotózás közben, és konkrét utasítás, melyik szögből kell még kép.
- **Blender ágens** (TERV 6.4): `bpy`-kódot ír a javításokhoz (lyukak, talp, tájolás), és renderrel ellenőrzi.
- **Alj pótlása**: második felvétel a tárgy megfordításával, a két háló automatikus összeillesztése.
