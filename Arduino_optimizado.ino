#include <Wire.h>

const uint8_t SFM3300_ADDR = 0x40;
const int BURB_PIN = A0;
const int REINICIO_PIN = A2;  // Pin para el botón de reinicio

unsigned int burb_count = 0;
int prevBurbState = HIGH;
int prevButtonState = HIGH;
unsigned long lastDebounceBurb = 0;
unsigned long lastDebounceButton = 0;
const unsigned long debounceDelayButton = 10;  // ms para botón
const unsigned long debounceDelayBurb = 200;   // ms para burbujas

// Función unificada para detectar flanco descendente con debounce no-bloqueante
bool detectFallingEdge(int pin, int &prevState, unsigned long &lastDebounce, unsigned long debounceDelay) {
  int currentState = digitalRead(pin);
  if (currentState == LOW && prevState == HIGH) {
    unsigned long currentTime = millis();
    if (currentTime - lastDebounce > debounceDelay) {
      lastDebounce = currentTime;
      prevState = currentState;
      return true;  // Flanco detectado
    }
  }
  prevState = currentState;
  return false;
}

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(BURB_PIN, INPUT);
  pinMode(REINICIO_PIN, INPUT_PULLUP);  // Pull-up interna

  delay(110);  // Combinado delays previos

  // Iniciar medición continua del sensor de flujo
  Wire.beginTransmission(SFM3300_ADDR);
  Wire.write(0x10);
  Wire.write(0x00);
  Wire.endTransmission();
}

uint16_t leerRawFlujo() {
  Wire.requestFrom(SFM3300_ADDR, 2);  // Solo 2 bytes (MSB+LSB), ignoramos CRC
  if (Wire.available() == 2) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    return ((uint16_t)msb << 8) | lsb;
  }
  return 0;
}

float convertirFlujo(uint16_t raw) {
  return -((float)raw - 32768.0) / 120.0;
}

void loop() {
  // Detección botón reinicio
  if (detectFallingEdge(REINICIO_PIN, prevButtonState, lastDebounceButton, debounceDelayButton)) {
    burb_count = 0;
  }

  // Detección burbuja
  if (detectFallingEdge(BURB_PIN, prevBurbState, lastDebounceBurb, debounceDelayBurb)) {
    burb_count++;
  }

  // Leer y enviar datos del sensor de flujo
  uint16_t raw_flujo = leerRawFlujo();
  float flujo = convertirFlujo(raw_flujo);

  // Print eficiente en una línea
  Serial.println(String(raw_flujo) + "," + String(flujo, 4) + "," + String(burb_count));

  // Sin delay final; el loop corre libre, pero si necesitas rate-limit, usa millis()
  // Ejemplo: static unsigned long lastLoop = 0; if (millis() - lastLoop < 10) return; lastLoop = millis();
}
