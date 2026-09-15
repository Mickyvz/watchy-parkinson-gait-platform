# -*- coding: utf-8 -*-
"""
Validacion de mediciones RPM: Watchy vs Mesa Biaxial Oscilatoria
Genera grafica de correlacion y metricas de validacion
"""

import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from scipy import stats

# Datos de validacion
# Eje Y: RPM reales de la mesa biaxial oscilatoria
# Eje X: RPM estimadas por el Watchy
rpm_mesa = np.array([25, 35, 50, 55, 60, 65, 70, 75])
rpm_watchy = np.array([25, 35, 50, 50, 60, 60, 65, 70])

# Calcular metricas de validacion
r2 = r2_score(rpm_mesa, rpm_watchy)
mae = mean_absolute_error(rpm_mesa, rpm_watchy)
rmse = np.sqrt(mean_squared_error(rpm_mesa, rpm_watchy))

# Regresion lineal
slope, intercept, r_value, p_value, std_err = stats.linregress(rpm_watchy, rpm_mesa)

# Crear figura
plt.figure(figsize=(10, 8))

# Scatter plot de los datos
plt.scatter(rpm_watchy, rpm_mesa, s=100, color='#2E86AB',
            alpha=0.7, edgecolors='black', linewidth=1.5,
            label='Mediciones', zorder=3)

# Linea de identidad perfecta (y = x)
min_val = min(rpm_watchy.min(), rpm_mesa.min()) - 5
max_val = max(rpm_watchy.max(), rpm_mesa.max()) + 5
plt.plot([min_val, max_val], [min_val, max_val],
         'k--', linewidth=2, alpha=0.5, label='Identidad perfecta (y=x)', zorder=1)

# Linea de regresion
x_reg = np.array([min_val, max_val])
y_reg = slope * x_reg + intercept
plt.plot(x_reg, y_reg, 'r-', linewidth=2, alpha=0.7,
         label=f'Regresion lineal (y={slope:.3f}x+{intercept:.2f})', zorder=2)

# Agregar anotaciones para cada punto
for i in range(len(rpm_mesa)):
    # Evitar sobreposicion de etiquetas
    offset_x = 1.5 if rpm_watchy[i] != rpm_mesa[i] else 0
    offset_y = 1.5 if rpm_watchy[i] != rpm_mesa[i] else 2
    plt.annotate(f'({rpm_watchy[i]}, {rpm_mesa[i]})',
                 (rpm_watchy[i], rpm_mesa[i]),
                 textcoords="offset points",
                 xytext=(offset_x, offset_y),
                 ha='left', fontsize=9, alpha=0.7)

# Configuracion de ejes
plt.xlabel('RPM estimadas por Watchy', fontsize=12, fontweight='bold')
plt.ylabel('RPM reales (Mesa Biaxial)', fontsize=12, fontweight='bold')
plt.title('Validacion de Mediciones RPM:\nWatchy vs Mesa Biaxial Oscilatoria',
          fontsize=14, fontweight='bold', pad=20)

# Grid
plt.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)

# Leyenda
plt.legend(loc='upper left', fontsize=10, framealpha=0.9)

# Anadir cuadro de texto con metricas
textstr = f'Metricas de Validacion:\n' \
          f'R2 = {r2:.4f}\n' \
          f'MAE = {mae:.2f} RPM\n' \
          f'RMSE = {rmse:.2f} RPM\n' \
          f'n = {len(rpm_mesa)} mediciones'

props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
plt.text(0.98, 0.02, textstr, transform=plt.gca().transAxes,
         fontsize=10, verticalalignment='bottom', horizontalalignment='right',
         bbox=props)

# Ajustar limites de ejes
plt.xlim(min_val, max_val)
plt.ylim(min_val, max_val)

# Aspecto cuadrado para mejor visualizacion
plt.gca().set_aspect('equal', adjustable='box')

# Ajustar layout
plt.tight_layout()

# Guardar figura
output_file = 'validacion_rpm_watchy.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Grafica guardada en: {output_file}")

# Mostrar figura
plt.show()

# Imprimir metricas detalladas
print("\n" + "="*50)
print("RESULTADOS DE VALIDACION")
print("="*50)
print(f"\nCoeficiente de Determinacion (R2): {r2:.4f}")
print(f"  -> Correlacion: {'Excelente' if r2 > 0.95 else 'Buena' if r2 > 0.90 else 'Moderada'}")
print(f"\nError Absoluto Medio (MAE): {mae:.2f} RPM")
print(f"Error Cuadratico Medio (RMSE): {rmse:.2f} RPM")
print(f"\nRegresion Lineal: y = {slope:.3f}x + {intercept:.2f}")
print(f"  -> Pendiente cercana a 1: {'Si' if abs(slope - 1) < 0.1 else 'No'}")
print(f"  -> Intercepto cercano a 0: {'Si' if abs(intercept) < 5 else 'No'}")
print(f"\nValor p: {p_value:.4e} (significativo si < 0.05)")

print("\n" + "="*50)
print("TABLA DE MEDICIONES")
print("="*50)
print(f"{'Mesa RPM':<12} {'Watchy RPM':<12} {'Error':<12} {'Error %':<12}")
print("-"*50)
for i in range(len(rpm_mesa)):
    error = rpm_watchy[i] - rpm_mesa[i]
    error_pct = (error / rpm_mesa[i]) * 100
    print(f"{rpm_mesa[i]:<12} {rpm_watchy[i]:<12} {error:<12.1f} {error_pct:<12.1f}")
print("="*50)

# Analisis de limitaciones
print("\n" + "="*50)
print("ANALISIS DE LIMITACIONES")
print("="*50)
print("\nLimitacion detectada en rango 55-65 RPM:")
print("  - 55 RPM -> 50 RPM estimado (error: -5 RPM, -9.1%)")
print("  - 60 RPM -> 60 RPM estimado (error: 0 RPM, 0%)")
print("  - 65 RPM -> 60 RPM estimado (error: -5 RPM, -7.7%)")
print("\nCausa: Valores raw indistinguibles (48.1-48.2 RPM)")
print("  -> Resolucion espectral insuficiente para distinguir estas velocidades")
print("  -> Limitacion del hardware del acelerometro Watchy")
print("\n" + "="*50)
