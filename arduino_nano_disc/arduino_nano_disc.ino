#include <Stepper.h>

const int lepesKor = 2048;   // 1 teljes fordulat (360°)
const int fokonkent = 10;    // Lépésköz fokban
const int szunetMs = 1500;   // Megállás ideje (1500 ms = 1,5 másodperc)

Stepper motor(lepesKor, 8, 10, 9, 11);

int eddigiLepes = 0;
int szamlalo = 0;

void setup() {
  motor.setSpeed(6); // Lassabb, finomabb indítás, hogy ne mozduljon el a modell
}

void loop() {
  szamlalo++;
  int celLepes = (long)lepesKor * (szamlalo * fokonkent) / 360;
  int mostaniLepes = celLepes - eddigiLepes;

  motor.step(mostaniLepes);  // Ha a másik irányba forogjon: -mostaniLepes
  eddigiLepes = celLepes;

  delay(szunetMs);

  // Teljes kör után nullázás
  if (szamlalo * fokonkent >= 360) {
    szamlalo = 0;
    eddigiLepes = 0;
  }
}
