#include <Wire.h>

const uint8_t SFM3300_ADDR = 0x40;
const int BURB_PIN = A0;
const int REINICIO_PIN = A2;  // Pin para el botón de reinicio

unsigned int burb_count = 0;
int prevState = HIGH;
int prevButtonState = HIGH;    // Estado previo del botón de reinicio
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;  // Tiempo de debounce en ms

void setup() {
  Serial.begin(115200);
  Wire.begin();

  pinMode(BURB_PIN, INPUT);
  pinMode(REINICIO_PIN, INPUT_PULLUP);  // Configurar con resistencia pull-up interna

  delay(100);

  // Iniciar medición continua del sensor de flujo
  Wire.beginTransmission(SFM3300_ADDR);
  Wire.write(0x10);
  Wire.write(0x00);
  Wire.endTransmission();

  delay(10);
}

uint16_t leerRawFlujo() {
  Wire.requestFrom(SFM3300_ADDR, 3);
  if (Wire.available() == 3) {
    uint8_t msb = Wire.read();
    uint8_t lsb = Wire.read();
    Wire.read();  // CRC ignorado
    return ((uint16_t)msb << 8) | lsb;
  }
  return 0;
}

float convertirFlujo(uint16_t raw) {
  return ((float)raw - 32768.0) / 120.0;
}

void loop() {
  // Leer estado del botón de reinicio
  int buttonState = digitalRead(REINICIO_PIN);
  
  // Detectar flanco descendente (botón presionado)
  if (buttonState == LOW && prevButtonState == HIGH) {
    unsigned long currentTime = millis();
    // Verificar debounce
    if (currentTime - lastDebounceTime > debounceDelay) {
      burb_count = 0;  // Reiniciar contador
      lastDebounceTime = currentTime;
    }
  }
  prevButtonState = buttonState;

  // Leer sensor de burbujas
  int currentState = digitalRead(BURB_PIN);
  
  // Detectar flanco descendente (burbuja)
  if (prevState == HIGH && currentState == LOW) {
    burb_count++;
    delay(200);  // Debounce para burbujas
  }
  prevState = currentState;

  // Leer y mostrar datos del sensor de flujo
  uint16_t raw_flujo = leerRawFlujo();
  float flujo = convertirFlujo(raw_flujo);

  Serial.print(raw_flujo);
  Serial.print(',');
  Serial.print(flujo, 4);
  Serial.print(',');
  Serial.println(burb_count);

  delay(10);
}