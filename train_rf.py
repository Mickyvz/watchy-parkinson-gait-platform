import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix

DATASET_PATH = "datasetw.csv"
MODEL_OUT = "rf_model.joblib"
FEATURES_OUT = "features_order.json"

def main():
    df = pd.read_csv(DATASET_PATH)

    if "label" not in df.columns:
        raise ValueError("No encuentro la columna 'label' en el dataset.")

    # Features = todas menos label
    feature_cols = [c for c in df.columns if c != "label"]
    X = df[feature_cols].astype(float).to_numpy()
    y = df["label"].astype(str).to_numpy()

    print("Clases:", np.unique(y))
    print("Distribución:\n", pd.Series(y).value_counts())

    # Modelo final (ajusta hiperparámetros si quieres)
    rf = RandomForestClassifier(
        n_estimators=500,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=2,
        max_features="sqrt",
        bootstrap=True,
        random_state=42,
        n_jobs=-1
    )

    # Evaluación rápida (estratificada)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    accs = cross_val_score(rf, X, y, cv=skf, scoring="accuracy", n_jobs=-1)
    print(f"\nAccuracy 5-fold: {accs.mean():.4f} (+/- {accs.std():.4f})")

    # Entrenar modelo final con TODO el dataset
    rf.fit(X, y)

    # Reporte entrenando y evaluando en el mismo (solo para ver consistencia, no reportar como CV)
    y_hat = rf.predict(X)
    print("\nConfusion (train on full data):")
    print(confusion_matrix(y, y_hat, labels=rf.classes_))
    print("\nClassification report (train on full data):")
    print(classification_report(y, y_hat))

    # Guardar modelo
    joblib.dump(rf, MODEL_OUT)
    print(f"\nModelo guardado en: {MODEL_OUT}")

    # Guardar orden de columnas
    with open(FEATURES_OUT, "w", encoding="utf-8") as f:
        json.dump(feature_cols, f, ensure_ascii=False, indent=2)
    print(f"Orden de features guardado en: {FEATURES_OUT}")

    # --- Feature Importance ---
    importances = rf.feature_importances_
    indices = np.argsort(importances)[::-1][:15]  # Top 15 features
    top_features = [feature_cols[i] for i in indices]
    top_importances = importances[indices]

    # Color gradient: darker = more important
    colors = plt.cm.Blues(np.linspace(0.35, 0.85, len(top_features)))

    _, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top_features[::-1], top_importances[::-1], color=colors, edgecolor="white", linewidth=0.5)
    ax.set_xlabel("Feature Importance (Gini Impurity)", fontsize=12)
    ax.set_title("Top 15 Most Important Features — Random Forest Classifier", fontsize=13, fontweight="bold")
    ax.bar_label(bars, fmt="%.3f", padding=3, fontsize=9)
    ax.set_xlim(0, max(top_importances) * 1.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="both", labelsize=10)
    ax.grid(axis="x", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig("feature_importance.png", dpi=300, bbox_inches="tight")
    plt.show()
    print("\nFigure saved: feature_importance.png")

    # Print ranking in console
    print("\nFeature importance ranking:")
    for rank, (feat, imp) in enumerate(zip(top_features, top_importances), 1):
        print(f"  {rank:2d}. {feat:<30s} {imp:.4f}")

    # --- Model Comparison ---
    print("\n" + "="*60)
    print("MODEL COMPARISON — Stratified 5-Fold Cross-Validation")
    print("="*60)

    models = {
        "Random Forest":       rf,
        "Gradient Boosting":   GradientBoostingClassifier(n_estimators=200, max_depth=4, random_state=42),
        "SVM (RBF)":           Pipeline([("scaler", StandardScaler()), ("svm", SVC(kernel="rbf", C=1.0, random_state=42))]),
        "k-NN (k=5)":          Pipeline([("scaler", StandardScaler()), ("knn", KNeighborsClassifier(n_neighbors=5))]),
        "Logistic Regression": Pipeline([("scaler", StandardScaler()), ("lr", LogisticRegression(max_iter=1000, random_state=42))]),
    }

    scoring = {"Accuracy": "accuracy", "F1 (macro)": "f1_macro", "Precision (macro)": "precision_macro", "Recall (macro)": "recall_macro"}
    results = {}

    for model_name, model in models.items():
        results[model_name] = {}
        for metric_name, metric in scoring.items():
            scores = cross_val_score(model, X, y, cv=skf, scoring=metric, n_jobs=-1)
            results[model_name][metric_name] = scores.mean()
        print(f"\n{model_name}")
        for metric_name, val in results[model_name].items():
            print(f"  {metric_name:<22s}: {val:.4f}")

    # --- Comparison table as DataFrame ---
    results_df = pd.DataFrame(results).T
    results_df = results_df.sort_values("Accuracy", ascending=False)
    print("\n\nSummary Table:")
    print(results_df.to_string(float_format="{:.4f}".format))
    results_df.to_csv("model_comparison.csv")
    print("\nTable saved: model_comparison.csv")

    # --- Comparison bar chart ---
    _, ax2 = plt.subplots(figsize=(11, 5))
    x = np.arange(len(results_df))
    width = 0.2
    metric_colors = ["#2166ac", "#4dac26", "#d01c8b", "#f1a340"]

    for i, (metric_name, color) in enumerate(zip(scoring.keys(), metric_colors)):
        vals = results_df[metric_name].values
        bars2 = ax2.bar(x + i * width, vals, width, label=metric_name, color=color, alpha=0.85, edgecolor="white")
        ax2.bar_label(bars2, fmt="%.2f", fontsize=7.5, padding=2)

    ax2.set_xticks(x + width * 1.5)
    ax2.set_xticklabels(results_df.index, fontsize=10)
    ax2.set_ylabel("Score", fontsize=12)
    ax2.set_ylim(0, 1.05)
    ax2.set_title("Model Comparison — Stratified 5-Fold Cross-Validation", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=12, loc="upper right", framealpha=0.9)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.grid(axis="y", linestyle="--", alpha=0.4)
    plt.tight_layout()
    plt.savefig("model_comparison.png", dpi=300, bbox_inches="tight")
    plt.show()
    print("Figure saved: model_comparison.png")

if __name__ == "__main__":
    main()
