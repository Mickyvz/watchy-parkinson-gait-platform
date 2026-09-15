"""
Random Forest (from scratch) + Stratified K-Fold CV (k=5)
- Multi-class: gait_normal / gait_fast / gait_slow
- Improvements for publication-ready evaluation
"""

import os
from datetime import datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


# =============================================================================
# DECISION TREE (CART-like) FROM SCRATCH
# =============================================================================
class DecisionTree:
    def __init__(self, max_depth=10, min_samples_split=2, min_samples_leaf=1, n_features=None, random_state=42):
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.n_features = n_features
        self.tree = None
        self.random_state = random_state
        self.rng = np.random.default_rng(random_state)

    def fit(self, X, y):
        self.n_features = X.shape[1] if not self.n_features else min(self.n_features, X.shape[1])
        self.tree = self._grow_tree(X, y)
        return self

    def _grow_tree(self, X, y, depth=0):
        n_samples, n_features = X.shape
        unique_labels = np.unique(y)

        # Stop criteria
        if (depth >= self.max_depth or
            len(unique_labels) == 1 or
            n_samples < self.min_samples_split):
            return {'leaf': True, 'value': self._most_common_label(y)}

        # Random feature subset
        feat_idxs = self.rng.choice(n_features, self.n_features, replace=False)

        # Best split
        best_feat, best_thresh, best_gain = self._best_split(X, y, feat_idxs)

        # If no valid split, create leaf
        if best_feat is None or best_thresh is None or best_gain <= 0:
            return {'leaf': True, 'value': self._most_common_label(y)}

        # Split data
        left_mask = X[:, best_feat] <= best_thresh
        right_mask = ~left_mask

        # Safety check (should be prevented by min_samples_leaf, but keep safe)
        if left_mask.sum() < self.min_samples_leaf or right_mask.sum() < self.min_samples_leaf:
            return {'leaf': True, 'value': self._most_common_label(y)}

        left = self._grow_tree(X[left_mask], y[left_mask], depth + 1)
        right = self._grow_tree(X[right_mask], y[right_mask], depth + 1)

        return {
            'leaf': False,
            'feature': best_feat,
            'threshold': best_thresh,
            'left': left,
            'right': right
        }

    def _best_split(self, X, y, feat_idxs):
        best_gain = -1.0
        best_feat = None
        best_thresh = None

        for feat_idx in feat_idxs:
            X_column = X[:, feat_idx]

            uniq = np.unique(X_column)
            if len(uniq) < 2:
                continue

            # Use midpoints between sorted unique values (better practice than raw values)
            thresholds = (uniq[:-1] + uniq[1:]) / 2.0

            for threshold in thresholds:
                gain = self._information_gain(y, X_column, threshold)

                if gain > best_gain:
                    best_gain = gain
                    best_feat = feat_idx
                    best_thresh = threshold

        return best_feat, best_thresh, best_gain

    def _information_gain(self, y, X_column, threshold):
        parent_gini = self._gini_impurity(y)

        left_mask = X_column <= threshold
        right_mask = ~left_mask

        n_left = left_mask.sum()
        n_right = right_mask.sum()

        # Enforce min_samples_leaf
        if n_left < self.min_samples_leaf or n_right < self.min_samples_leaf:
            return 0.0

        n = len(y)
        gini_left = self._gini_impurity(y[left_mask])
        gini_right = self._gini_impurity(y[right_mask])

        child_gini = (n_left / n) * gini_left + (n_right / n) * gini_right
        return parent_gini - child_gini

    def _gini_impurity(self, y):
        _, counts = np.unique(y, return_counts=True)
        probs = counts / len(y)
        return 1.0 - np.sum(probs ** 2)

    def _most_common_label(self, y):
        unique, counts = np.unique(y, return_counts=True)
        return unique[np.argmax(counts)]

    def predict(self, X):
        return np.array([self._traverse_tree(x, self.tree) for x in X])

    def _traverse_tree(self, x, node):
        if node['leaf']:
            return node['value']
        if x[node['feature']] <= node['threshold']:
            return self._traverse_tree(x, node['left'])
        return self._traverse_tree(x, node['right'])


# =============================================================================
# RANDOM FOREST FROM SCRATCH
# =============================================================================
class RandomForest:
    def __init__(self, n_trees=100, max_depth=10, min_samples_split=2, min_samples_leaf=1,
                 n_features=None, random_state=42):
        self.n_trees = n_trees
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.n_features = n_features
        self.random_state = random_state
        self.rng = np.random.default_rng(random_state)
        self.trees = []

    def fit(self, X, y):
        self.trees = []
        n_samples = X.shape[0]

        for t in range(self.n_trees):
            # Bootstrap sampling
            idxs = self.rng.integers(0, n_samples, size=n_samples)
            X_sample, y_sample = X[idxs], y[idxs]

            tree = DecisionTree(
                max_depth=self.max_depth,
                min_samples_split=self.min_samples_split,
                min_samples_leaf=self.min_samples_leaf,
                n_features=self.n_features,
                random_state=int(self.rng.integers(0, 1_000_000))
            )
            tree.fit(X_sample, y_sample)
            self.trees.append(tree)

        return self

    def predict(self, X):
        # Predictions from all trees: shape (n_trees, n_samples)
        tree_preds = np.array([tree.predict(X) for tree in self.trees])

        # Majority vote per sample
        y_pred = []
        for i in range(X.shape[0]):
            votes, counts = np.unique(tree_preds[:, i], return_counts=True)
            y_pred.append(votes[np.argmax(counts)])
        return np.array(y_pred)


# =============================================================================
# STRATIFIED K-FOLD (FROM SCRATCH)
# =============================================================================
def stratified_kfold_indices(y, k=5, seed=42):
    rng = np.random.default_rng(seed)
    y = np.array(y)

    folds = [[] for _ in range(k)]
    for cls in np.unique(y):
        idx = np.where(y == cls)[0]
        rng.shuffle(idx)
        parts = np.array_split(idx, k)
        for i in range(k):
            folds[i].extend(parts[i].tolist())

    # Convert to numpy arrays
    folds = [np.array(fold, dtype=int) for fold in folds]
    return folds


def stratified_k_fold_cross_validation(X, y, k=5, seed=42,
                                       n_trees=100, max_depth=10,
                                       min_samples_split=2, min_samples_leaf=1,
                                       n_features=None):
    folds = stratified_kfold_indices(y, k=k, seed=seed)

    fold_accuracies = []
    fold_predictions = []
    fold_true_labels = []

    print(f"Iniciando Stratified {k}-Fold CV con Random Forest ({n_trees} árboles)...\n")

    all_idx = np.arange(len(y))
    for fold_idx in range(k):
        test_indices = folds[fold_idx]
        test_set = set(test_indices.tolist())
        train_indices = np.array([i for i in all_idx if i not in test_set], dtype=int)

        X_train, X_test = X[train_indices], X[test_indices]
        y_train, y_test = y[train_indices], y[test_indices]

        rf = RandomForest(
            n_trees=n_trees,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            n_features=n_features,
            random_state=seed + fold_idx  # change seed per fold but reproducible
        )
        rf.fit(X_train, y_train)
        y_pred = rf.predict(X_test)

        acc = np.mean(y_pred == y_test)
        fold_accuracies.append(acc)
        fold_predictions.append(y_pred)
        fold_true_labels.append(y_test)

        print(f"Fold {fold_idx+1}/{k}: train={len(train_indices)} test={len(test_indices)}  accuracy={acc:.4f}")

    all_predictions = np.concatenate(fold_predictions)
    all_true_labels = np.concatenate(fold_true_labels)

    mean_acc = float(np.mean(fold_accuracies))
    std_acc = float(np.std(fold_accuracies))

    print("\n" + "=" * 60)
    print("RESULTADOS FINALES (Stratified K-Fold)")
    print(f"Accuracy por fold: {[f'{a:.4f}' for a in fold_accuracies]}")
    print(f"Accuracy promedio: {mean_acc:.4f} (+/- {std_acc:.4f})")
    print("=" * 60)

    return {
        "fold_accuracies": fold_accuracies,
        "mean_accuracy": mean_acc,
        "std_accuracy": std_acc,
        "all_predictions": all_predictions,
        "all_true_labels": all_true_labels
    }


# =============================================================================
# CONFUSION MATRIX + METRICS (MULTICLASS)
# =============================================================================
def create_confusion_matrix(y_true, y_pred, class_labels):
    n_classes = len(class_labels)
    cm = np.zeros((n_classes, n_classes), dtype=int)
    label_to_idx = {lab: i for i, lab in enumerate(class_labels)}

    for t, p in zip(y_true, y_pred):
        cm[label_to_idx[t], label_to_idx[p]] += 1
    return cm


def macro_f1_from_confusion(cm):
    # rows=true, cols=pred
    f1s = []
    for i in range(cm.shape[0]):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
        f1s.append(f1)
    return float(np.mean(f1s))


def plot_confusion_matrix(cm, class_labels, title='Matriz de Confusión', save_path=None):
    plt.figure(figsize=(9, 7))
    sns.heatmap(
        cm, annot=True, fmt='d', cmap='Blues',
        xticklabels=class_labels, yticklabels=class_labels,
        cbar_kws={'label': 'Número de muestras'},
        linewidths=0.5, linecolor='gray'
    )
    plt.title(title, fontsize=14, fontweight='bold', pad=15)
    plt.ylabel('Clase Verdadera', fontsize=11, fontweight='bold')
    plt.xlabel('Clase Predicha', fontsize=11, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nMatriz de confusión guardada en: {save_path}")

    plt.show()


def calculate_metrics_per_class(y_true, y_pred, class_labels):
    metrics = {}
    for label in class_labels:
        y_true_bin = (y_true == label).astype(int)
        y_pred_bin = (y_pred == label).astype(int)

        TP = np.sum((y_true_bin == 1) & (y_pred_bin == 1))
        TN = np.sum((y_true_bin == 0) & (y_pred_bin == 0))
        FP = np.sum((y_true_bin == 0) & (y_pred_bin == 1))
        FN = np.sum((y_true_bin == 1) & (y_pred_bin == 0))

        recall = TP / (TP + FN) if (TP + FN) else 0.0
        precision = TP / (TP + FP) if (TP + FP) else 0.0
        specificity = TN / (TN + FP) if (TN + FP) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        bal_acc = (recall + specificity) / 2.0

        metrics[label] = {
            "TP": TP, "TN": TN, "FP": FP, "FN": FN,
            "Precision": precision, "Recall": recall,
            "Specificity": specificity, "F1": f1,
            "Balanced Accuracy": bal_acc
        }
    return metrics


def print_metrics_table(metrics):
    rows = []
    for label, m in metrics.items():
        rows.append({
            "Clase": label,
            "Precision": m["Precision"],
            "Recall": m["Recall"],
            "F1": m["F1"],
            "Specificity": m["Specificity"],
            "Balanced Accuracy": m["Balanced Accuracy"]
        })
    dfm = pd.DataFrame(rows)

    macro_row = {
        "Clase": "MACRO AVG",
        "Precision": dfm["Precision"].mean(),
        "Recall": dfm["Recall"].mean(),
        "F1": dfm["F1"].mean(),
        "Specificity": dfm["Specificity"].mean(),
        "Balanced Accuracy": dfm["Balanced Accuracy"].mean()
    }
    dfm = pd.concat([dfm, pd.DataFrame([macro_row])], ignore_index=True)

    print("\n" + "=" * 90)
    print("MÉTRICAS POR CLASE (One-vs-Rest) + MACRO AVG")
    print("=" * 90)
    print(dfm.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("=" * 90)
    return dfm


# =============================================================================
# SAVE SUMMARY
# =============================================================================
def save_summary(output_path, results, macro_f1, metrics_df, cm_df):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("RANDOM FOREST (FROM SCRATCH) - STRATIFIED K-FOLD CV\n")
        f.write("=" * 80 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("Accuracy por fold:\n")
        f.write(str([round(a, 4) for a in results["fold_accuracies"]]) + "\n")
        f.write(f"\nAccuracy promedio: {results['mean_accuracy']:.4f} (+/- {results['std_accuracy']:.4f})\n")
        f.write(f"Macro-F1: {macro_f1:.4f}\n\n")

        f.write("\nMatriz de confusión (rows=true, cols=pred):\n")
        f.write(cm_df.to_string() + "\n\n")

        f.write("\nMétricas por clase:\n")
        f.write(metrics_df.to_string(index=False) + "\n")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 80)
    print("RANDOM FOREST (FROM SCRATCH) + STRATIFIED K-FOLD CV")
    print("=" * 80)

    # Output dir
    output_dir = "resultados_algoritmo"
    os.makedirs(output_dir, exist_ok=True)

    # Load data
    df = pd.read_csv("datasetw.csv")
    print(f"\nDataset shape: {df.shape}")
    print("Distribución de clases:\n", df["label"].value_counts())

    X = df.drop("label", axis=1).values.astype(float)
    y = df["label"].values.astype(str)

    # Hyperparameters (reasonable defaults for your dataset size)
    seed = 42
    k = 5
    n_features_sqrt = int(np.sqrt(X.shape[1]))

    results = stratified_k_fold_cross_validation(
        X=X, y=y, k=k, seed=seed,
        n_trees=200,
        max_depth=12,
        min_samples_split=2,
        min_samples_leaf=2,   # recommended for stability
        n_features=n_features_sqrt
    )

    # Confusion matrix
    class_labels = np.unique(y)  # keep original string labels
    cm = create_confusion_matrix(results["all_true_labels"], results["all_predictions"], class_labels)

    cm_df = pd.DataFrame(cm, index=class_labels, columns=class_labels)

    # Macro-F1
    macro_f1 = macro_f1_from_confusion(cm)

    print(f"\nMacro-F1: {macro_f1:.4f}")

    # Plot confusion matrix
    plot_confusion_matrix(
        cm, class_labels,
        title=f"Matriz de Confusión - RF from scratch (Stratified {k}-Fold)",
        save_path=os.path.join(output_dir, "confusion_matrix.png")
    )

    # Metrics per class
    metrics = calculate_metrics_per_class(results["all_true_labels"], results["all_predictions"], class_labels)
    metrics_df = print_metrics_table(metrics)

    metrics_csv_path = os.path.join(output_dir, "metricas_desempeno.csv")
    metrics_df.to_csv(metrics_csv_path, index=False)
    print(f"\nMétricas guardadas en: {metrics_csv_path}")

    # Save summary
    summary_path = os.path.join(output_dir, "resumen_completo.txt")
    save_summary(summary_path, results, macro_f1, metrics_df, cm_df)
    print(f"Resumen guardado en: {summary_path}")

    print("\n" + "=" * 80)
    print("PROCESO COMPLETADO")
    print(f"Resultados en: {output_dir}")
    print("=" * 80)


if __name__ == "__main__":
    main()
