import os
import csv
import datetime

# Nombre fijo del archivo
filename = "sensor_data_combined.csv"

# ID único para cada corrida (puede ser timestamp corto)
corrida_id = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

if times or bubble_times:
    # Verificar si el archivo ya existe
    file_exists = os.path.isfile(filename)

    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)

        # Escribir cabecera solo si el archivo no existía
        if not file_exists:
            writer.writerow([
                'corrida_id',
                'bubble_time_s',
                'vol_por_burbuja_L',
                'vol_por_burbuja_error_L',
                'temp_C',
                'press_hPa',
                'raw_flujo',
                'flow_crudo_slm',
                'flow_filtrado_slm',
                'flow_filtrado_error_slm',
                'volume_total_L',
                'volume_total_error_L',
                'burb_count',
                'new_bubbles'
            ])

        # Guardar cada burbuja como una fila con todos los datos asociados
        for j in range(len(bubble_times)):
            # Para cada burbuja usamos datos "globales" de la corrida
            writer.writerow([
                corrida_id,
                bubble_times[j],
                bubble_volumes[j],
                bubble_vol_errors[j],
                bubble_temps[j],
                bubble_pressures[j],
                raw_flujos[j] if j < len(raw_flujos) else None,
                flows[j] if j < len(flows) else None,
                flows_filtered[j] if j < len(flows_filtered) else None,
                flows_filtered_errors[j] if j < len(flows_filtered_errors) else None,
                volumes[j] if j < len(volumes) else None,
                volumes_errors[j] if j < len(volumes_errors) else None,
                burb_counts[j] if j < len(burb_counts) else None,
                new_bubbles_list[j] if j < len(new_bubbles_list) else None
            ])

    print(f"Datos de la corrida {corrida_id} añadidos a {filename}")
else:
    print("No hay datos para guardar en CSV.")