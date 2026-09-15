import pandas as pd
import numpy as np
from sklearn.model_selection import LeaveOneOut, cross_val_score, cross_val_predict
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline import Pipeline
import matplotlib.pyplot as plt
import seaborn as sns
import joblib

# Cargar dataset
df = pd.read_csv('tremor_fog_dataset.csv')

print("="*70)
print("ENTRENAMIENTO CON LEAVE-ONE-OUT CROSS-VALIDATION")
print("="*70)

print("\n=== INFORMACIÓN DEL DATASET ===")
print(f"Total muestras: {len(df)}")
print(f"\nDistribución de clases:")
print(df['label'].value_counts())

# Separar features y labels
metadata_cols = ['captureId', 'label', 'subjectId', 'activityContext', 
                 'captureDate', 'timestamp', 'sampleRate', 'duration', 'numSamples']
feature_cols = [col for col in df.columns if col not in metadata_cols]

X = df[feature_cols]
y = df['label']

print(f"\nCaracterísticas utilizadas: {len(feature_cols)}")

# ========== LEAVE-ONE-OUT CROSS-VALIDATION ==========
print("\n" + "="*70)
print("LEAVE-ONE-OUT CROSS-VALIDATION")
print("="*70)
print(f"\nCada muestra será usada como test una vez")
print(f"Total de iteraciones: {len(df)}")

# Crear pipeline con normalizador + clasificador
# Importante: el scaler debe estar dentro del pipeline para LOOCV
pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        random_state=42,
        class_weight='balanced'
    ))
])

# Leave-One-Out CV
loo = LeaveOneOut()

# Obtener predicciones para cada fold
print("\n--- Predicciones por fold ---")
y_pred_loo = cross_val_predict(pipeline, X, y, cv=loo)

# Scores por fold
cv_scores = cross_val_score(pipeline, X, y, cv=loo, scoring='accuracy')

print("\nResultados por iteración (fold):")
print("Iteración | Real        | Predicho    | Correcto")
print("-" * 55)
for i, (real, pred, score) in enumerate(zip(y, y_pred_loo, cv_scores), 1):
    correct = "✓" if real == pred else "✗"
    print(f"{i:9d} | {real:11s} | {pred:11s} | {correct} ({score:.0f})")

# Resultados globales
print("\n" + "="*70)
print("RESULTADOS GLOBALES")
print("="*70)

accuracy_loo = accuracy_score(y, y_pred_loo)
print(f"\nAccuracy (Leave-One-Out): {accuracy_loo:.3f} ({accuracy_loo*100:.1f}%)")
print(f"Muestras correctamente clasificadas: {(y == y_pred_loo).sum()}/{len(y)}")
print(f"Muestras mal clasificadas: {(y != y_pred_loo).sum()}/{len(y)}")

print("\n=== REPORTE DE CLASIFICACIÓN ===")
try:
    report = classification_report(y, y_pred_loo, zero_division=0)
    print(report)
except Exception as e:
    print(f"⚠ No se pudo generar reporte completo: {e}")
    # Reporte manual
    for label in y.unique():
        mask = y == label
        correct = ((y == y_pred_loo) & mask).sum()
        total = mask.sum()
        print(f"{label}: {correct}/{total} ({correct/total*100:.1f}%)")

# Matriz de confusión
print("\n=== MATRIZ DE CONFUSIÓN ===")
cm = confusion_matrix(y, y_pred_loo, labels=sorted(y.unique()))
cm_df = pd.DataFrame(cm, 
                     index=sorted(y.unique()), 
                     columns=sorted(y.unique()))
print(cm_df)

# Visualizar matriz de confusión
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
            xticklabels=sorted(y.unique()), 
            yticklabels=sorted(y.unique()),
            cbar_kws={'label': 'Número de muestras'})
plt.title(f'Matriz de Confusión (LOOCV)\nAccuracy: {accuracy_loo*100:.1f}%', 
          fontsize=14, fontweight='bold')
plt.ylabel('Clase Real', fontsize=12)
plt.xlabel('Clase Predicha', fontsize=12)
plt.tight_layout()
plt.savefig('confusion_matrix_loocv.png', dpi=300, bbox_inches='tight')
print("\n✓ Matriz de confusión guardada: confusion_matrix_loocv.png")

# ========== ENTRENAR MODELO FINAL CON TODOS LOS DATOS ==========
print("\n" + "="*70)
print("ENTRENAMIENTO DEL MODELO FINAL")
print("="*70)
print("\nEntrenando modelo con TODAS las muestras para predicciones futuras...")

# Normalizar todos los datos
scaler_final = StandardScaler()
X_scaled_all = scaler_final.fit_transform(X)

# Entrenar modelo final
clf_final = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    random_state=42,
    class_weight='balanced'
)
clf_final.fit(X_scaled_all, y)

print("✓ Modelo final entrenado con todas las muestras")

# Feature importance del modelo final
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': clf_final.feature_importances_
}).sort_values('importance', ascending=False)

print("\n=== TOP 15 CARACTERÍSTICAS MÁS IMPORTANTES ===")
print(feature_importance.head(15).to_string(index=False))

# Graficar importancias
plt.figure(figsize=(12, 8))
top_features = feature_importance.head(20)
colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(top_features)))
plt.barh(range(len(top_features)), top_features['importance'], color=colors)
plt.yticks(range(len(top_features)), top_features['feature'], fontsize=10)
plt.xlabel('Importancia', fontsize=12)
plt.title('Top 20 Características Más Importantes', fontsize=14, fontweight='bold')
plt.grid(axis='x', alpha=0.3)
plt.tight_layout()
plt.savefig('feature_importance_loocv.png', dpi=300, bbox_inches='tight')
print("\n✓ Importancia de features guardada: feature_importance_loocv.png")

# ========== ANÁLISIS DETALLADO POR CLASE ==========
print("\n" + "="*70)
print("ANÁLISIS DETALLADO POR CLASE")
print("="*70)

for label in sorted(y.unique()):
    mask = y == label
    predicted_mask = y_pred_loo == label
    
    # Métricas por clase
    true_positives = ((y == label) & (y_pred_loo == label)).sum()
    false_positives = ((y != label) & (y_pred_loo == label)).sum()
    false_negatives = ((y == label) & (y_pred_loo != label)).sum()
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print(f"\n{label.upper()}:")
    print(f"  Muestras totales: {mask.sum()}")
    print(f"  Correctamente clasificadas: {true_positives}")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall: {recall:.3f}")
    print(f"  F1-Score: {f1:.3f}")

# ========== GUARDAR MODELO ==========
print("\n" + "="*70)
print("GUARDANDO MODELO Y ARCHIVOS")
print("="*70)

joblib.dump(clf_final, 'tremor_fog_classifier.pkl')
joblib.dump(scaler_final, 'scaler.pkl')
joblib.dump(feature_cols, 'feature_columns.pkl')

print("\n✓ Modelo guardado: tremor_fog_classifier.pkl")
print("✓ Scaler guardado: scaler.pkl")
print("✓ Columnas guardadas: feature_columns.pkl")

# Guardar resumen
with open('loocv_results.txt', 'w') as f:
    f.write("RESULTADOS DE LEAVE-ONE-OUT CROSS-VALIDATION\n")
    f.write("=" * 60 + "\n\n")
    f.write(f"Total de muestras: {len(df)}\n")
    f.write(f"Accuracy: {accuracy_loo:.3f} ({accuracy_loo*100:.1f}%)\n")
    f.write(f"Correctas: {(y == y_pred_loo).sum()}/{len(y)}\n\n")
    f.write("Matriz de Confusión:\n")
    f.write(str(cm_df))
    f.write("\n\nTop 10 Features:\n")
    f.write(feature_importance.head(10).to_string(index=False))

print("✓ Resumen guardado: loocv_results.txt")

# ========== VISUALIZACIÓN FINAL ==========
print("\n" + "="*70)
print("GENERANDO VISUALIZACIONES FINALES")
print("="*70)

# Gráfica de resultados por muestra
fig, axes = plt.subplots(1, 2, figsize=(15, 6))

# 1. Resultados individuales
sample_ids = range(1, len(y) + 1)
colors_result = ['green' if r == p else 'red' for r, p in zip(y, y_pred_loo)]
axes[0].scatter(sample_ids, [1]*len(y), c=colors_result, s=200, alpha=0.6)
axes[0].set_xlabel('Número de Muestra', fontsize=12)
axes[0].set_ylabel('Resultado', fontsize=12)
axes[0].set_title('Resultados de Clasificación por Muestra\n(Verde=Correcto, Rojo=Incorrecto)', 
                  fontsize=12, fontweight='bold')
axes[0].set_yticks([1])
axes[0].set_yticklabels([''])
axes[0].grid(True, alpha=0.3, axis='x')
axes[0].set_xlim(0, len(y) + 1)

# Añadir etiquetas
for i, (r, p) in enumerate(zip(y, y_pred_loo), 1):
    axes[0].text(i, 1.05, f'{r}\n→{p}', ha='center', va='bottom', fontsize=8)

# 2. Distribución de accuracy por clase
class_accuracies = []
class_names = []
for label in sorted(y.unique()):
    mask = y == label
    acc = (y[mask] == y_pred_loo[mask]).mean()
    class_accuracies.append(acc * 100)
    class_names.append(label)

colors_bar = ['green' if acc == 100 else 'orange' if acc >= 50 else 'red' 
              for acc in class_accuracies]
axes[1].bar(class_names, class_accuracies, color=colors_bar, alpha=0.7, edgecolor='black')
axes[1].axhline(y=100, color='green', linestyle='--', alpha=0.5, label='100%')
axes[1].set_ylabel('Accuracy (%)', fontsize=12)
axes[1].set_xlabel('Clase', fontsize=12)
axes[1].set_title('Accuracy por Clase (LOOCV)', fontsize=12, fontweight='bold')
axes[1].set_ylim(0, 110)
axes[1].legend()
axes[1].grid(True, alpha=0.3, axis='y')

# Añadir valores en las barras
for i, (name, acc) in enumerate(zip(class_names, class_accuracies)):
    axes[1].text(i, acc + 3, f'{acc:.1f}%', ha='center', fontweight='bold')

plt.tight_layout()
plt.savefig('loocv_detailed_results.png', dpi=300, bbox_inches='tight')
print("\n✓ Resultados detallados guardados: loocv_detailed_results.png")

print("\n" + "="*70)
print("✓✓✓ ENTRENAMIENTO COMPLETADO ✓✓✓")
print("="*70)
print(f"\nAccuracy final (LOOCV): {accuracy_loo*100:.1f}%")
print(f"Archivos generados:")
print("  - tremor_fog_classifier.pkl")
print("  - scaler.pkl")
print("  - feature_columns.pkl")
print("  - confusion_matrix_loocv.png")
print("  - feature_importance_loocv.png")
print("  - loocv_detailed_results.png")
print("  - loocv_results.txt")

plt.show()