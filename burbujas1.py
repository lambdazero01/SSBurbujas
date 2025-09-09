import serial
import time

# Configura el puerto serial según tu setup (ej. 'COM3' en Windows, '/dev/ttyUSB0' en Linux/Mac)
SERIAL_PORT = 'COM3'  # Cambia esto al puerto correcto
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

volume_total = 0.0
prev_time = time.time()
prev_count = 0

print("Iniciando lectura de datos del sensor...")
print("Presiona Ctrl+C para detener.")

try:
    while True:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            parts = line.split(',')
            if len(parts) == 3:
                try:
                    raw_flujo = int(parts[0])
                    flujo = float(parts[1])
                    burb_count = int(parts[2])

                    curr_time = time.time()
                    dt = curr_time - prev_time
                    prev_time = curr_time

                    # Integrar el flujo para calcular volumen (flujo en slm, dt en segundos -> volumen en litros)
                    volume_total += flujo * (dt / 60.0)

                    # Detectar reinicio (cuando el contador de burbujas se resetea)
                    if burb_count < prev_count:
                        volume_total = 0.0

                    prev_count = burb_count

                    if burb_count > 0:
                        vol_por_burbuja = volume_total / burb_count
                    else:
                        vol_por_burbuja = 0.0

                    print(f"Flujo: {flujo:.4f} slm, Burbujas: {burb_count}, Volumen Total: {volume_total:.4f} L, Volumen por Burbuja: {vol_por_burbuja:.4f} L")
                except ValueError:
                    print("Error al parsear línea:", line)
        time.sleep(0.01)  # Pequeño delay para no saturar CPU
except KeyboardInterrupt:
    print("Deteniendo...")
finally:
    ser.close()