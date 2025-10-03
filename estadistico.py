import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols
import matplotlib.pyplot as plt

# === 1. Cargar CSV ===
df = pd.read_csv("sensor_data_combined.csv")

# Asegúrate de que no haya NaN en columnas críticas
df = df.dropna(subset=['vol_por_burbuja_L', 'press_hPa', 'flow_filtrado_slm', 'temp_C'])

print("Primeras filas del dataset:\n", df.head())

# === 2. ANOVA ===
model = ols('vol_por_burbuja_L ~ press_hPa + flow_filtrado_slm + temp_C', data=df).fit()
anova_table = sm.stats.anova_lm(model, typ=2)

print("\n--- Resultados ANOVA ---")
print(anova_table)

# === 3. Estadística descriptiva del volumen ===
mean_vol = df['vol_por_burbuja_L'].mean()
std_vol = df['vol_por_burbuja_L'].std()
var_vol = df['vol_por_burbuja_L'].var()

print("\n--- Estadística descriptiva del volumen de burbujas ---")
print(f"Media: {mean_vol:.6f} L")
print(f"Desviación estándar: {std_vol:.6f} L")
print(f"Varianza: {var_vol:.6f} L^2")

# === 4. Gráficas de dispersión ===
variables = ['press_hPa', 'temp_C', 'flow_filtrado_slm', 'raw_flujo', 'volume_total_L']

for var in variables:
    if var in df.columns:
        plt.figure()
        plt.scatter(df[var], df['vol_por_burbuja_L'], alpha=0.6)
        plt.xlabel(var)
        plt.ylabel("vol_por_burbuja_L")
        plt.title(f"Volumen de burbuja vs {var}")
        plt.grid(True)
        plt.tight_layout()
        plt.show()