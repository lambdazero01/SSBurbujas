import serial
import time
import matplotlib.pyplot as plt
import numpy as np
import csv
import datetime
import requests  # Para API
import json      # Para parsear JSON

# Configura el puerto serial
SERIAL_PORT = 'COM3'  # Cambia esto al puerto de tu sensor (e.g., 'COM4')
BAUD_RATE = 115200

ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)

# Tu clave API de WeatherAPI (regístrate en https://www.weatherapi.com/)
API_KEY = '386200d430724947832204653251809'  # Reemplaza con tu clave real, e.g., 'abcd1234efgh5678'

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

offset = calibrate_offset()  # Ejecuta al inicio

# Función para obtener clima de WeatherAPI
def obtener_clima(lat, lon):
    """
    Obtiene temperatura y presión de WeatherAPI.
    lat/lon: Coordenadas GPS (e.g., 19.4326 para lat de Mexico City, -99.1332 para lon).
    Retorna (temp, press) o (None, None) si falla.
    """
    try:
        # URL para datos actuales: https://api.weatherapi.com/v1/current.json
        url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={lat},{lon}&aqi=no"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            temp = data['current']['temp_c']  # En °C
            press = data['current']['pressure_mb']  # En hPa (milibares)
            print(f"Clima actualizado (WeatherAPI): Temp={temp}°C, Press={press} hPa")
            return temp, press
        else:
            print(f"Error en API: {response.status_code} - {response.text}")
            return None, None
    except Exception as e:
        print(f"Error al consultar API: {e}")
        return None, None

# Configuración de ubicación (pide al inicio; usa coordenadas o ciudad)
print("Configurando ubicación para clima...")
ubicacion_input = input("Ingresa latitud y longitud (e.g., 19.4326,-99.1332) o ciudad (e.g., Mexico City): ").strip()
if ',' in ubicacion_input:
    lat, lon = map(float, ubicacion_input.split(','))
else:
    # Si es ciudad, usa coordenadas aproximadas
    ubicacion_lower = ubicacion_input.lower()
    if "mexico" in ubicacion_lower:
        lat, lon = 19.4326, -99.1332
    elif "bogota" in ubicacion_lower:
        lat, lon = 4.7110, -74.0721
    elif "buenos aires" in ubicacion_lower:
        lat, lon = -34.6037, -58.3816
    else:
        lat, lon = 0, 0  # Default; ajusta manualmente
    print(f"Usando coordenadas aproximadas para '{ubicacion_input}': lat={lat}, lon={lon}")

# Obtener clima inicial
temp_actual, press_actual = obtener_clima(lat, lon)
if temp_actual is None:
    print("No se pudo obtener clima inicial. Usando valores por defecto (25°C, 1013 hPa).")
    temp_actual, press_actual = 25.0, 1013.0

last_clima_update = time.time()  # Para actualizar cada 60s
update_interval = 60  # Segundos entre actualizaciones de clima

volume_total = 0.0
start_time = time.time()
prev_time = start_time
prev_count = 0
flujo_filtered = 0.0  # Inicial para EMA
alpha = 0.1  # Factor EMA (0-1; menor = más suavizado, pero más lag)
noise_threshold = 0.2  # slm; ignora flujo < este valor (de datasheet)

times = []
flows = []  # Crudos
flows_filtered = []  # Filtrados
volumes = []
bubble_times = []
raw_flujos = []
burb_counts = []
new_bubbles_list = []
temps = []  # Ahora dinámica
pressures = []  # Ahora dinámica
bubble_temps = []  # Temp al momento de cada burbuja
bubble_pressures = []  # Press al momento de cada burbuja

print("Iniciando lectura de datos del sensor...")
print(f"Clima inicial: Temp={temp_actual}°C, Press={press_actual} hPa. Actualizando cada {update_interval}s.")
print("Presiona Ctrl+C para detener y generar las gráficas.")

try:
    while True:
        # Actualizar clima cada intervalo
        if time.time() - last_clima_update >= update_interval:
            temp_actual, press_actual = obtener_clima(lat, lon)
            if temp_actual is not None:
                last_clima_update = time.time()
            else:
                # Mantén el último valor válido si falla
                pass

        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            parts = line.split(',')
            if len(parts) == 3:
                try:
                    raw_flujo = int(parts[0])
                    flujo = float(parts[1]) - offset  # Resta offset
                    burb_count = int(parts[2])

                    # Filtro EMA
                    flujo_filtered = alpha * flujo + (1 - alpha) * flujo_filtered

                    # Clip a positivo (asumiendo flujo unidireccional)
                    flujo_filtered = max(0.0, flujo_filtered)

                    curr_time = time.time() - start_time
                    dt = curr_time - prev_time
                    prev_time = curr_time

                    # Integrar solo si > umbral de ruido
                    if abs(flujo_filtered) > noise_threshold:
                        volume_total += flujo_filtered * (dt / 60.0)

                    # Detección de reinicio y burbujas
                    new_bubbles = 0
                    if burb_count < prev_count:
                        volume_total = 0.0

                    if burb_count > prev_count:
                        new_bubbles = burb_count - prev_count
                        for _ in range(new_bubbles):
                            bubble_times.append(curr_time)
                            bubble_temps.append(temp_actual)  # Asigna temp actual a cada burbuja
                            bubble_pressures.append(press_actual)  # Asigna press actual a cada burbuja

                    prev_count = burb_count

                    if burb_count > 0:
                        vol_por_burbuja = volume_total / burb_count
                    else:
                        vol_por_burbuja = 0.0

                    # Almacenar para gráficas y CSV
                    times.append(curr_time)
                    raw_flujos.append(raw_flujo)
                    flows.append(flujo)
                    flows_filtered.append(flujo_filtered)
                    volumes.append(volume_total)
                    burb_counts.append(burb_count)
                    new_bubbles_list.append(new_bubbles)
                    temps.append(temp_actual)
                    pressures.append(press_actual)

                    print(f"Flujo crudo: {flujo:.4f} slm, Flujo filtrado: {flujo_filtered:.4f} slm, Burbujas: {burb_count}, Volumen Total: {volume_total:.4f} L, Volumen por Burbuja: {vol_por_burbuja:.4f} L, Temp: {temp_actual}°C, Press: {press_actual} hPa")
                except ValueError:
                    print("Error al parsear línea:", line)
        time.sleep(0.01)
except KeyboardInterrupt:
    print("Deteniendo y generando gráficas...")
finally:
    ser.close()

# Generar gráficas (agregando temp y press)
if times:
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

    # Gráfica 1: Flujo y volumen
    ax1.plot(times, flows, 'b-', label='Flujo crudo (slm)', alpha=0.7)
    ax1.plot(times, flows_filtered, 'm-', label='Flujo filtrado (slm)')
    ax1.set_xlabel('Tiempo (s)')
    ax1.set_ylabel('Flujo (slm)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1_twin = ax1.twinx()
    ax1_twin.plot(times, volumes, 'g-', label='Volumen Total (L)')
    ax1_twin.set_ylabel('Volumen (L)', color='g')
    ax1_twin.tick_params(axis='y', labelcolor='g')
    if bubble_times:
        ax1.vlines(bubble_times, ymin=np.min(flows) if flows else 0, ymax=np.max(flows) if flows else 1, colors='r', linestyles='dashed', label='Burbujas')
    ax1.legend(loc='upper left')

    # Gráfica 2: Temperatura y presión
    ax2.plot(times, temps, 'orange', label='Temperatura (°C)')
    ax2.set_xlabel('Tiempo (s)')
    ax2.set_ylabel('Temperatura (°C)', color='orange')
    ax2_twin2 = ax2.twinx()
    ax2_twin2.plot(times, pressures, 'purple', label='Presión (hPa)')
    ax2_twin2.set_ylabel('Presión (hPa)', color='purple')
    ax2.legend(loc='upper left')
    ax2_twin2.legend(loc='upper right')

    # Gráfica 3: Volumen por burbuja vs tiempo (aprox, usa promedio)
    if bubble_times and burb_count > 0:
        vol_avg_bubble = volume_total / burb_count
        ax3.plot(bubble_times, [vol_avg_bubble] * len(bubble_times), 'ko-', label='Volumen por burbuja (L, aprox)')
        ax3.set_xlabel('Tiempo (s)')
        ax3.set_ylabel('Volumen por burbuja (L)')
        ax3.legend()

    # Gráfica 4: Scatter volumen vs temp/press (para burbujas)
    if bubble_vols := [volume_total / burb_count if burb_count > 0 else 0] * len(bubble_times):  # Aprox
        ax4.scatter(bubble_temps, [vol_avg_bubble] * len(bubble_temps), color='orange', label='vs Temp')
        ax4.scatter(bubble_pressures, [vol_avg_bubble] * len(bubble_pressures), color='purple', label='vs Press')
        ax4.set_xlabel('Temp (°C) / Press (hPa)')
        ax4.set_ylabel('Volumen por burbuja (L)')
        ax4.legend()

    plt.suptitle('Flujo, Volumen, Temp, Press y Burbujas a lo largo del Tiempo (WeatherAPI)')
    plt.tight_layout()
    plt.show()
else:
    print("No hay datos para graficar.")

# Generar CSV con los datos (incluyendo temp y press dinámicos)
if times:
    filename = datetime.datetime.now().strftime('sensor_data_%Y%m%d_%H%M%S.csv')
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['time_s', 'raw_flujo', 'flow_crudo_slm', 'flow_filtrado_slm', 'volume_total_L', 'burb_count', 'new_bubbles', 'temp_C', 'press_hPa'])
        for i in range(len(times)):
            writer.writerow([times[i], raw_flujos[i], flows[i], flows_filtered[i], volumes[i], burb_counts[i], new_bubbles_list[i], temps[i], pressures[i]])
    print(f"Datos guardados en {filename}")
    
    # CSV de burbujas individuales con temp/press al momento
    if bubble_times:
        bubble_filename = filename.replace('.csv', '_bubbles.csv')
        with open(bubble_filename, 'w', newline='') as f_bub:
            writer_bub = csv.writer(f_bub)
            writer_bub.writerow(['bubble_time_s', 'vol_por_burbuja_L', 'temp_C', 'press_hPa'])
            vol_avg_bubble = volume_total / burb_count if burb_count > 0 else 0.0  # Aprox; ajusta si necesitas individual
            for j in range(len(bubble_times)):
                writer_bub.writerow([bubble_times[j], vol_avg_bubble, bubble_temps[j], bubble_pressures[j]])
        print(f"Datos de burbujas individuales guardados en {bubble_filename}")
else:
    print("No hay datos para guardar en CSV.")