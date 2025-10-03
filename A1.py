import pandas as pd
import glob

# Ruta donde están tus CSVs (ajusta si no están en la misma carpeta)
ruta = "./"  

# Buscar todos los CSV que empiecen con "sensor_data_combined"
archivos = glob.glob(ruta + "sensor_data_combined_*.csv")

# Lista para almacenar los DataFrames
dataframes = []

for archivo in archivos:
    try:
        df = pd.read_csv(archivo)
        dataframes.append(df)
    except Exception as e:
        print(f"No se pudo leer {archivo}: {e}")

# Concatenar todos los DataFrames
df_final = pd.concat(dataframes, ignore_index=True)

# Guardar en un único CSV
df_final.to_csv("sensor_data_unificado.csv", index=False)

print(f"CSV unificado generado: sensor_data_unificado.csv")