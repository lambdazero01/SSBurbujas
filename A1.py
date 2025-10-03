import pandas as pd

# Archivo ya unificado pero mezclado
archivo = "sensor_data_unificado.csv"

# Listas para almacenar las líneas de cada sección
lineas_times = []
lineas_burbujas = []

# Estado: estamos leyendo qué parte?
parte_burbujas = False

with open(archivo, "r") as f:
    for linea in f:
        # Detectar separador
        if "--- DATOS DE BURBUJAS" in linea:
            parte_burbujas = True
            continue  # saltamos esta línea
        
        # Guardar en la parte correspondiente
        if parte_burbujas:
            lineas_burbujas.append(linea)
        else:
            lineas_times.append(linea)

# Guardar en archivos temporales limpios
with open("temp_times.csv", "w") as f:
    f.writelines(lineas_times)

with open("temp_burbujas.csv", "w") as f:
    f.writelines(lineas_burbujas)

# Cargar con pandas (ignora filas vacías)
df_times = pd.read_csv("temp_times.csv").dropna(how="all")
df_burbujas = pd.read_csv("temp_burbujas.csv").dropna(how="all")

# Guardar los CSV finales
df_times.to_csv("sensor_data_unificado_times.csv", index=False)
df_burbujas.to_csv("sensor_data_unificado_burbujas.csv", index=False)

print("✅ Se han creado:")
print("  - sensor_data_unificado_times.csv (datos principales)")
print("  - sensor_data_unificado_burbujas.csv (datos de burbujas)")