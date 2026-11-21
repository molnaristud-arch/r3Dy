# Motoros forgóasztal – 28BYJ-48 léptetőmotor + Arduino

A motor 10°-onként lép és megáll; **minden megállásnál kézzel exponálunk** (a soros monitor `FOTO k/36` sora jelzi a megállást). Zümmer nincs és nem is kell. Folyamatos módban 1 RPM-mel forog a videós felvételhez.

**A mi összeállításunk:** Arduino Nano + ULN2003 meghajtópanel + 28BYJ-48 5 V léptetőmotor.

## Alkatrészek (~3–5 000 Ft)

| db | alkatrész | megjegyzés |
|---|---|---|
| 1 | 28BYJ-48 5 V léptetőmotor + ULN2003 meghajtópanel | általában együtt árulják |
| 1 | Arduino Uno vagy Nano (klón is jó) + USB-kábel | |
| (1) | piezo zümmer | **nem használjuk** – csak automatikus, hangvezérelt exponáláshoz kellene |
| 1 | nyomógomb | opcionális – soros monitorról is vezérelhető |
| ~8 | anya–anya / apa–anya jumper kábel | |

## Bekötés

```
ULN2003 IN1 → D8      ULN2003 +  → 5V
ULN2003 IN2 → D9      ULN2003 -  → GND
ULN2003 IN3 → D10     motor 5 eres csatlakozója → ULN2003 aljzat (csak egy irányban megy be)
ULN2003 IN4 → D11
gomb        → D2 és GND között (opcionális; belső felhúzó ellenállás, nem kell külön)
(zümmer      → D7 és GND – nincs bekötve; a program sípszója nélküle hatástalan)
```

Egy motorhoz elég az USB-táp (a motor ~250 mA-t vesz fel).

## Feltöltés

1. Arduino IDE → **File → Open** → `turntable_stepper/turntable_stepper.ino`.
2. **Tools → Board**: Arduino Uno (vagy Nano; klón Nanónál **Processor: ATmega328P (Old Bootloader)**).
3. **Tools → Port**: `/dev/ttyUSB0` vagy `/dev/ttyACM0`. Linuxon ha nem engedi: `sudo usermod -aG dialout $USER`, majd ki- és bejelentkezés.
4. **Upload**. Utána **Tools → Serial Monitor**, 115200 baud, „Newline” sorvég → megjelenik: `Forgoasztal kesz…`

## Használat

| parancs (soros monitor) | gomb | hatás |
|---|---|---|
| `s` | megnyom | léptető mód: 36 megállás 10°-onként – **mindegyiknél egy fotó kézzel** |
| `c` | – | folyamatos forgás (`r` RPM, alap 1.0) – videós módhoz |
| `x` | megnyom futás közben | stop |
| `?` | – | állapot |
| `n36` | – | megállások száma körönként (4–360) |
| `d2500` | – | ennyi ms-ig áll minden megállásnál (300–60000) |
| `r1.0` | – | RPM folyamatos módban (max 10) |
| `b0` / `b1` | – | sípszó ki / be (zümmer nélkül mindegy) |

Egy megállás: lassan induló és lassan fékező 10°-os elfordulás (~0,3 s) → 0,6 s várakozás, hogy a tárgy ne rezegjen → **`FOTO k/36` – itt exponálunk** → 2,5 s állás. **Egy kör 36 fotóval ~2 perc.** Kör végén megáll; emeld meg a telefont, és indítsd újra a második körhöz.

A Nano bekapcsoláskor az alapértékekkel indul (`n36`, `d2500`): ha kényelmesebb tempó kell, minden indítás után add ki pl. a `d4000` parancsot.

## Telefon: kézi exponálás

1. **A telefon legyen rögzítve** (állvány, tartó vagy könyvkupac), 40–50 cm-re, az 1. körben ~20°-kal, a 2. körben ~45°-kal a tárgy fölött; tájolás (álló/fekvő) a két körben azonos.
2. **Fókusz és expozíció zárolva** (Open Camera: *Locked* + AE lock; iPhone: hosszan nyomva a tárgyra → „AE/AF ZÁR”), legnagyobb felbontás, HDR, vaku, éjszakai mód ki, 1× zoom. iPhone-on a formátum JPG legyen (Beállítások → Kamera → Formátumok → Legkompatibilisebb).
3. **Exponálás minden megállásnál:** a tányér megáll → fél másodperc → egy érintés. A telefont ne told el; ha az érintés megmozdítja, használj 2 s-os időzítőt (és `d4000`-et), vagy a hangerőgombot / távkioldót.
4. **Nem kell pontosan 36 kép körönként:** egy kihagyott vagy dupla kép nem baj, a szoftver a képek tartalmából számolja a helyzetüket.

## Mechanika

- A motor tengelye 5 mm-es, két oldalán lelapolt. A tányért (hab- vagy rétegelt lemez, a nyomtatott koronggal) **pontosan középen** rögzítsd: tengelycsatlakozó, vagy a lapba fúrt furat + ragasztó.
- A motor **nem csapágy**: 300 g fölötti tárgynál a tányér súlyát vegye át egy forgócsapágy (lazy susan) vagy egy **áram nélküli PC-ventilátor** csapágya, a motor csak forgasson (pl. gumigyűrűs / súrlódókerekes hajtással a tányér pereménél).
- A motor és a meghajtópanel melegszik, ha áram alatt áll: a program álló helyzetben lekapcsolja a tekercseket (a fogaskerékhajtás így is megtartja a tányért).

## Tesztelés hardver nélkül

`../stepper_sim/run.sh` – a vázlatot a PC-n egy minimális Arduino-utánzattal fordítja le és szimulált idővel futtatja (36 megállás 9,98–10,07°-onként, folyamatos módban 60 s alatt pontosan 1,000 fordulat, parancsok, gomb). Változtatás után futtasd le.
