import serial
import time
import matplotlib.pyplot as plt
import numpy as np
import csv
import datetime
import requests  # Para API
import math  # Para sqrt

# Configura el puerto serial
SERIAL_PORT = 'COM3'  # Cambia esto al puerto de tu sensor (e.g., 'COM4')
BAUD_RATE = 115200

# Tu clave API de WeatherAPI
API_KEY = '386200d430724947832204653251809'

# Calibración de offset: promedio de lecturas en cero flujo
def calibrate_offset(ser, num_samples=100):
    print("Calibrando offset: asegúrate de que no haya flujo...")
    offsets = []
    for _ in range(num_samples):
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line:
            parts = line.split(',')
            if len(parts) == 3:
                flujo = float(parts[1])
                offsets.append(max(0.0, flujo))  # Clip a positivo en calibración
        time.sleep(0.01)
    offset = np.mean(offsets) if offsets else 0.0
    print(f"Offset calibrado: {offset:.4f} slm")
    return offset

# Función para obtener clima de WeatherAPI con retry simple
def obtener_clima(lat, lon, retries=3):
    for attempt in range(retries):
        try:
            url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={lat},{lon}&aqi=no"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                temp = data['current']['temp_c']  # En °C
                press = data['current']['pressure_mb']  # En hPa (milibares)
                print(f"Clima actualizado (WeatherAPI): Temp={temp}°C, Press={press} hPa")
                return temp, press
            else:
                print(f"Error en API (intento {attempt+1}): {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Error al consultar API (intento {attempt+1}): {e}")
        time.sleep(2)  # Espera antes de retry
    print("Falló obtener clima después de retries. Usando últimos valores.")
    return None, None

# Coordenadas fijas para Puebla
lat, lon = 19.0036, -97.8883
print(f"Usando coordenadas fijas para Puebla: lat={lat}, lon={lon}")

# Altitude para corrección de presión (para Puebla)
altitude = 2165  # metros sobre el nivel del mar

with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
    offset = calibrate_offset(ser)  # Ejecuta al inicio

    # Obtener clima inicial
    temp_actual, press_mslp = obtener_clima(lat, lon)
    if temp_actual is None:
        print("No se pudo obtener clima inicial. Usando valores por defecto (25°C, 1013 hPa).")
        temp_actual, press_mslp = 25.0, 1013.0

    # Estimar presión local desde MSLP y altitud
    press_actual = press_mslp - altitude * 0.12  # 0.12 hPa por metro (aprox lapse rate)
    print(f"Presión ajustada para altitud {altitude}m: {press_actual:.1f} hPa")

    last_clima_update = time.time()  # Para actualizar cada 60s
    update_interval = 60  # Segundos entre actualizaciones de clima

    volume_total = 0.0
    delta_volume_error_total = 0.0  # Acumulador de error para volumen total (RSS)
    volume_since_last_bubble = 0.0  # Acumulador para volumen entre burbujas
    delta_volume_error_since_last = 0.0  # Acumulador de error para volumen entre burbujas (RSS)
    start_time = time.time()
    prev_time = start_time
    prev_count = 0
    flujo_filtered = 0.0  # Inicial para EMA
    alpha = 0.2  # Aumentado para respuesta más rápida
    noise_threshold = 0.0  # Eliminado para incluir todo el flujo

    # Condiciones estándar para slm (ajusta si tu sensor usa diferentes)
    T_std = 293.15  # K (20°C)
    P_std = 1013.0  # hPa

    # Errores estimados para clima
    delta_temp = 1.0  # °C
    delta_press = 1.0  # hPa

    # Especificaciones del sensor SFM3300 (max error conservador)
    flow_accuracy_rel_low = 0.05  # 5% m.v. para |flujo| < 100 slm
    flow_accuracy_rel_high = 0.002  # 0.2% m.v. para |flujo| > 100 slm
    flow_offset_error = 0.2  # slm

    times = []
    flows = []  # Crudos
    flows_filtered = []  # Filtrados
    flows_filtered_errors = []  # Errores de flujo filtrado
    volumes = []
    volumes_errors = []  # Errores de volumen total
    bubble_times = []
    raw_flujos = []
    burb_counts = []
    new_bubbles_list = []
    temps = []  # Ahora dinámica
    pressures = []  # Ahora dinámica
    bubble_temps = []  # Temp al momento de cada burbuja
    bubble_pressures = []  # Press al momento de cada burbuja
    bubble_volumes = []  # Volúmenes individuales por burbuja
    bubble_vol_errors = []  # Errores de volúmenes individuales

    print("Iniciando lectura de datos del sensor...")
    print(f"Clima inicial: Temp={temp_actual}°C, Press local={press_actual:.1f} hPa. Actualizando cada {update_interval}s.")
    print("Presiona Ctrl+C para detener y generar las gráficas.")

    try:
        while True:
            # Actualizar clima cada intervalo
            if time.time() - last_clima_update >= update_interval:
                new_temp, new_press_mslp = obtener_clima(lat, lon)
                if new_temp is not None:
                    temp_actual, press_mslp = new_temp, new_press_mslp
                    press_actual = press_mslp - altitude * 0.12
                    last_clima_update = time.time()

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

                        # Calcular factor de corrección T/P para volumen actual
                        T_k = temp_actual + 273.15
                        factor = (T_k / T_std) * (P_std / press_actual)

                        # Calcular error relativo para factor
                        rel_delta_factor = (delta_temp / T_k) + (delta_press / press_actual)

                        delta_factor = factor * rel_delta_factor

                        # Integrar si > umbral de ruido
                        delta_volume = 0.0
                        delta_volume_error = 0.0
                        if abs(flujo_filtered) > noise_threshold:
                            delta_volume = flujo_filtered * (dt / 60.0) * factor

                            # Calcular error en flujo
                            if flujo_filtered < 100:
                                delta_flow_span = flow_accuracy_rel_low * flujo_filtered
                            else:
                                delta_flow_span = flow_accuracy_rel_high * flujo_filtered
                            delta_flow = delta_flow_span + flow_offset_error

                            # Propagación de error para delta_volume
                            term1 = (delta_flow * (dt / 60.0) * factor) ** 2
                            term2 = (flujo_filtered * (dt / 60.0) * delta_factor) ** 2
                            delta_volume_error = math.sqrt(term1 + term2)

                            volume_total += delta_volume
                            volume_since_last_bubble += delta_volume

                            # Acumuladores de error (RSS)
                            delta_volume_error_total = math.sqrt(delta_volume_error_total ** 2 + delta_volume_error ** 2)
                            delta_volume_error_since_last = math.sqrt(delta_volume_error_since_last ** 2 + delta_volume_error ** 2)

                        # Detección de reinicio y burbujas
                        new_bubbles = 0
                        vol_per_bubble = 0.0
                        delta_vol_per_bubble = 0.0
                        if burb_count < prev_count:
                            volume_total = 0.0
                            delta_volume_error_total = 0.0
                            volume_since_last_bubble = 0.0
                            delta_volume_error_since_last = 0.0

                        if burb_count > prev_count:
                            new_bubbles = burb_count - prev_count
                            if new_bubbles > 0 and volume_since_last_bubble > 0:
                                vol_per_bubble = volume_since_last_bubble / new_bubbles
                                delta_vol_per_bubble = delta_volume_error_since_last / new_bubbles
                            for _ in range(new_bubbles):
                                bubble_times.append(curr_time)
                                bubble_temps.append(temp_actual)
                                bubble_pressures.append(press_actual)
                                bubble_volumes.append(vol_per_bubble)
                                bubble_vol_errors.append(delta_vol_per_bubble)
                            volume_since_last_bubble = 0.0
                            delta_volume_error_since_last = 0.0  # Reset después de asignar

                        prev_count = burb_count

                        if burb_count > 0:
                            vol_por_burbuja_avg = volume_total / burb_count
                        else:
                            vol_por_burbuja_avg = 0.0

                        # Almacenar para gráficas y CSV
                        times.append(curr_time)
                        raw_flujos.append(raw_flujo)
                        flows.append(flujo)
                        flows_filtered.append(flujo_filtered)
                        flows_filtered_errors.append(delta_flow if 'delta_flow' in locals() else 0.0)
                        volumes.append(volume_total)
                        volumes_errors.append(delta_volume_error_total)
                        burb_counts.append(burb_count)
                        new_bubbles_list.append(new_bubbles)
                        temps.append(temp_actual)
                        pressures.append(press_actual)

                        print(f"Flujo crudo: {flujo:.4f} slm, Flujo filtrado: {flujo_filtered:.4f} ± {flows_filtered_errors[-1]:.4f} slm, Burbujas: {burb_count}, Volumen Total: {volume_total:.4f} ± {delta_volume_error_total:.4f} L, Volumen Promedio por Burbuja: {vol_por_burbuja_avg:.4f} L, Temp: {temp_actual}°C, Press: {press_actual:.1f} hPa, Factor corrección: {factor:.2f}")
                        if new_bubbles > 0:
                            print(f"Nueva(s) burbuja(s) detectada(s): {new_bubbles}, Volumen individual aproximado: {vol_per_bubble:.4f} ± {delta_vol_per_bubble:.4f} L")
                    except ValueError:
                        print("Error al parsear línea:", line)
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Deteniendo y generando gráficas...")

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

    # Calcular vol_avg una vez (para compatibilidad, pero ahora usamos individuales)
    vol_avg_bubble = volume_total / burb_counts[-1] if burb_counts and burb_counts[-1] > 0 else 0.0

    # Gráfica 3: Volumen por burbuja vs tiempo (usando volúmenes individuales)
    if bubble_times and bubble_volumes:
        ax3.plot(bubble_times, bubble_volumes, 'ko-', label='Volumen por burbuja (L)')
        ax3.set_xlabel('Tiempo (s)')
        ax3.set_ylabel('Volumen por burbuja (L)')
        ax3.legend()

    # Gráfica 4: Scatter volumen vs temp/press (para burbujas, usando individuales)
    if bubble_times and bubble_volumes:
        ax4.scatter(bubble_temps, bubble_volumes, color='orange', label='vs Temp')
        ax4.scatter(bubble_pressures, bubble_volumes, color='purple', label='vs Press')
        ax4.set_xlabel('Temp (°C) / Press (hPa)')
        ax4.set_ylabel('Volumen por burbuja (L)')
        ax4.legend()

    plt.suptitle('Flujo, Volumen, Temp, Press y Burbujas a lo largo del Tiempo (Puebla, WeatherAPI)')
    plt.tight_layout()
    plt.show()
else:
    print("No hay datos para graficar.")

# Generar un solo CSV combinado con datos principales y de burbujas
if times or bubble_times:
    filename = datetime.datetime.now().strftime('sensor_data_combined_%Y%m%d_%H%M%S.csv')
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        # Cabecera y datos principales (time-series)
        writer.writerow(['time_s', 'raw_flujo', 'flow_crudo_slm', 'flow_filtrado_slm', 'flow_filtrado_error_slm', 'volume_total_L', 'volume_total_error_L', 'burb_count', 'new_bubbles', 'temp_C', 'press_hPa'])
        for i in range(len(times)):
            writer.writerow([times[i], raw_flujos[i], flows[i], flows_filtered[i], flows_filtered_errors[i], volumes[i], volumes_errors[i], burb_counts[i], new_bubbles_list[i], temps[i], pressures[i]])
        
        # Línea separadora
        writer.writerow([])
        writer.writerow(['--- DATOS DE BURBUJAS INDIVIDUALES ---'])
        
        # Cabecera y datos de burbujas
        writer.writerow(['bubble_time_s', 'vol_por_burbuja_L', 'vol_por_burbuja_error_L', 'temp_C', 'press_hPa'])
        for j in range(len(bubble_times)):
            writer.writerow([bubble_times[j], bubble_volumes[j], bubble_vol_errors[j], bubble_temps[j], bubble_pressures[j]])
    
    print(f"Datos combinados guardados en {filename}")
else:
    print("No hay datos para guardar en CSV.")