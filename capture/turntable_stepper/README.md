# Motoros forgóasztal – 28BYJ-48 léptetőmotor + Arduino

A kézi forgatás helyett a motor 10°-onként lép, megáll, sípol, és a telefon a sípszóra exponál (Open Camera hangvezérlés). Folyamatos módban 1 RPM-mel forog a videós felvételhez.

## Alkatrészek (~3–5 000 Ft)

| db | alkatrész | megjegyzés |
|---|---|---|
| 1 | 28BYJ-48 5 V léptetőmotor + ULN2003 meghajtópanel | általában együtt árulják |
| 1 | Arduino Uno vagy Nano (klón is jó) + USB-kábel | |
| 1 | piezo zümmer (aktív vagy passzív) | a fotó indításához |
| 1 | nyomógomb | opcionális – soros monitorról is vezérelhető |
| ~8 | anya–anya / apa–anya jumper kábel | |

## Bekötés

```
ULN2003 IN1 → D8      ULN2003 +  → 5V
ULN2003 IN2 → D9      ULN2003 -  → GND
ULN2003 IN3 → D10     motor 5 eres csatlakozója → ULN2003 aljzat (csak egy irányban megy be)
ULN2003 IN4 → D11
zümmer +    → D7      zümmer -   → GND
gomb        → D2 és GND között (belső felhúzó ellenállás, nem kell külön)
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
| `s` | megnyom | léptető mód: 36 megállás 10°-onként, mindegyiknél sípszó → fotó |
| `c` | – | folyamatos forgás (`r` RPM, alap 1.0) – videós módhoz |
| `x` | megnyom futás közben | stop |
| `?` | – | állapot |
| `n36` | – | megállások száma körönként (4–360) |
| `d2500` | – | ennyi ms-ig áll minden megállásnál (300–60000) |
| `r1.0` | – | RPM folyamatos módban (max 10) |
| `b0` / `b1` | – | sípszó ki / be |

Egy megállás: lassan induló és lassan fékező 10°-os elfordulás (~0,3 s) → 0,6 s várakozás, hogy a tárgy ne rezegjen → **sípszó (itt exponál a telefon)** → 2,5 s állás. **Egy kör 36 fotóval ~2 perc.** Kör végén megáll; emeld meg a telefont, és indítsd újra a második körhöz.

## Telefon: exponálás sípszóra (Open Camera)

1. Open Camera → Beállítások → **Távvezérlés** (Remote controls) → **Hangvezérlés** (Audio control) → **Zaj** (Loud noise). Az érzékenységet állítsd közepesre / magasra.
2. A kamera képernyőn megjelenik egy **mikrofon ikon**: koppints rá, ekkor kezd figyelni (az ikon pirosra vált).
3. Próba: `s` → minden sípszónál kattan a telefon. Ha nem: zümmert közelebb a telefonhoz, érzékenység feljebb. Ha két fotót készít egy sípszóra vagy beszédre is exponál: érzékenység lejjebb, a szoba legyen csendes.

(A menüpontok neve verziónként kicsit eltérhet. Ha a hangvezérlés nem megy, a `d6000` hosszabb állással kézzel / Bluetooth-os távkioldóval is kényelmesen lehet fotózni.)

## Mechanika

- A motor tengelye 5 mm-es, két oldalán lelapolt. A tányért (hab- vagy rétegelt lemez, a nyomtatott koronggal) **pontosan középen** rögzítsd: tengelycsatlakozó, vagy a lapba fúrt furat + ragasztó.
- A motor **nem csapágy**: 300 g fölötti tárgynál a tányér súlyát vegye át egy forgócsapágy (lazy susan) vagy egy **áram nélküli PC-ventilátor** csapágya, a motor csak forgasson (pl. gumigyűrűs / súrlódókerekes hajtással a tányér pereménél).
- A motor és a meghajtópanel melegszik, ha áram alatt áll: a program álló helyzetben lekapcsolja a tekercseket (a fogaskerékhajtás így is megtartja a tányért).

## Tesztelés hardver nélkül

`../stepper_sim/run.sh` – a vázlatot a PC-n egy minimális Arduino-utánzattal fordítja le és szimulált idővel futtatja (36 megállás 9,98–10,07°-onként, folyamatos módban 60 s alatt pontosan 1,000 fordulat, parancsok, gomb). Változtatás után futtasd le.
