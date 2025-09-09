import serial
import time
import matplotlib.pyplot as plt
import numpy as np

# Configura el puerto serial según tu setup (ej. 'COM3' en Windows, '/dev/ttyUSB0' en Linux/Mac)
SERIAL_PORT = 'COM3'  # Cambia esto al puerto correcto
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

volume_total = 0.0
start_time = time.time()
prev_time = start_time
prev_count = 0

times = []
flows = []
volumes = []
bubble_times = []

print("Iniciando lectura de datos del sensor...")
print("Presiona Ctrl+C para detener y generar las gráficas.")

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

                    curr_time = time.time() - start_time  # Tiempo relativo
                    dt = curr_time - prev_time
                    prev_time = curr_time

                    # Integrar el flujo para calcular volumen (flujo en slm, dt en segundos -> volumen en litros)
                    volume_total += flujo * (dt / 60.0)

                    # Detectar reinicio (cuando el contador de burbujas se resetea)
                    if burb_count < prev_count:
                        volume_total = 0.0
                        # Opcional: limpiar listas para reiniciar gráficas, pero por ahora mantenemos todo
                        # times = []
                        # flows = []
                        # volumes = []
                        # bubble_times = []
                        # start_time = time.time()
                        # curr_time = 0
                        # prev_time = curr_time

                    # Detectar nuevas burbujas
                    if burb_count > prev_count:
                        new_bubbles = burb_count - prev_count
                        for _ in range(new_bubbles):
                            bubble_times.append(curr_time)

                    prev_count = burb_count

                    if burb_count > 0:
                        vol_por_burbuja = volume_total / burb_count
                    else:
                        vol_por_burbuja = 0.0

                    # Almacenar datos para gráficas
                    times.append(curr_time)
                    flows.append(flujo)
                    volumes.append(volume_total)

                    print(f"Flujo: {flujo:.4f} slm, Burbujas: {burb_count}, Volumen Total: {volume_total:.4f} L, Volumen por Burbuja: {vol_por_burbuja:.4f} L")
                except ValueError:
                    print("Error al parsear línea:", line)
        time.sleep(0.01)  # Pequeño delay para no saturar CPU
except KeyboardInterrupt:
    print("Deteniendo y generando gráficas...")
finally:
    ser.close()

# Generar gráficas
if times:
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Gráfica de flujo vs tiempo
    ax1.plot(times, flows, 'b-', label='Flujo (slm)')
    ax1.set_xlabel('Tiempo (s)')
    ax1.set_ylabel('Flujo (slm)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')

    # Eje secundario para volumen total
    ax2 = ax1.twinx()
    ax2.plot(times, volumes, 'g-', label='Volumen Total (L)')
    ax2.set_ylabel('Volumen (L)', color='g')
    ax2.tick_params(axis='y', labelcolor='g')

    # Marcar burbujas con líneas verticales
    if bubble_times:
        ax1.vlines(bubble_times, ymin=np.min(flows) if flows else 0, ymax=np.max(flows) if flows else 1, colors='r', linestyles='dashed', label='Burbujas')

    # Leyendas
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.title('Flujo, Volumen y Burbujas a lo largo del Tiempo')
    plt.grid(True)
    plt.show()
else:
    print("No hay datos para graficar.")