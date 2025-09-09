import serial
import time
import matplotlib.pyplot as plt
import numpy as np

# Configura el puerto serial
SERIAL_PORT = 'COM3'  # Cambia esto
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

# Calibración de offset: promedio de lecturas en cero flujo
def calibrate_offset(num_samples=100):
    print("Calibrando offset: asegúrate de que no haya flujo...")
    offsets = []
    for _ in range(num_samples):
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            parts = line.split(',')
            if len(parts) == 3:
                flujo = float(parts[1])
                offsets.append(flujo)
        time.sleep(0.01)
    offset = np.mean(offsets) if offsets else 0.0
    print(f"Offset calibrado: {offset:.4f} slm")
    return offset

offset = calibrate_offset()  # Ejecuta calibración al inicio

volume_total = 0.0
start_time = time.time()
prev_time = start_time
prev_count = 0
flujo_filtered = 0.0  # Inicial para EMA
alpha = 0.2  # Factor de suavizado EMA (0-1; menor = más suavizado)

times = []
flows = []  # Flujos crudos
flows_filtered = []  # Flujos filtrados
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
                    flujo = float(parts[1]) - offset  # Resta offset calibrado
                    burb_count = int(parts[2])

                    # Filtro EMA
                    flujo_filtered = alpha * flujo + (1 - alpha) * flujo_filtered

                    # Opcional: Ignora picos extremos (ej. si >3x el filtrado previo)
                    # if abs(flujo) > 3 * abs(flujo_filtered):
                    #     flujo_filtered = prev_flujo_filtered  # Usa anterior
                    # prev_flujo_filtered = flujo_filtered

                    curr_time = time.time() - start_time
                    dt = curr_time - prev_time
                    prev_time = curr_time

                    # Integrar flujo filtrado (en L)
                    volume_total += flujo_filtered * (dt / 60.0)

                    # Resto del código igual (detección de burbujas, etc.)
                    if burb_count < prev_count:
                        volume_total = 0.0

                    if burb_count > prev_count:
                        new_bubbles = burb_count - prev_count
                        for _ in range(new_bubbles):
                            bubble_times.append(curr_time)

                    prev_count = burb_count

                    if burb_count > 0:
                        vol_por_burbuja = volume_total / burb_count
                    else:
                        vol_por_burbuja = 0.0

                    times.append(curr_time)
                    flows.append(flujo)  # Crudo para gráfica
                    flows_filtered.append(flujo_filtered)  # Filtrado
                    volumes.append(volume_total)

                    print(f"Flujo crudo: {flujo:.4f} slm, Flujo filtrado: {flujo_filtered:.4f} slm, Burbujas: {burb_count}, Volumen Total: {volume_total:.4f} L, Volumen por Burbuja: {vol_por_burbuja:.4f} L")
                except ValueError:
                    print("Error al parsear línea:", line)
        time.sleep(0.01)
except KeyboardInterrupt:
    print("Deteniendo y generando gráficas...")
finally:
    ser.close()

# Generar gráficas (agrega flujo filtrado)
if times:
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.plot(times, flows, 'b-', label='Flujo crudo (slm)')
    ax1.plot(times, flows_filtered, 'm-', label='Flujo filtrado (slm)')  # Nuevo
    ax1.set_xlabel('Tiempo (s)')
    ax1.set_ylabel('Flujo (slm)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')

    ax2 = ax1.twinx()
    ax2.plot(times, volumes, 'g-', label='Volumen Total (L)')
    ax2.set_ylabel('Volumen (L)', color='g')
    ax2.tick_params(axis='y', labelcolor='g')

    if bubble_times:
        ax1.vlines(bubble_times, ymin=np.min(flows) if flows else 0, ymax=np.max(flows) if flows else 1, colors='r', linestyles='dashed', label='Burbujas')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.title('Flujo, Volumen y Burbujas a lo largo del Tiempo')
    plt.grid(True)
    plt.show()
else:
    print("No hay datos para graficar.")