"""
Random Forest classifier for Phase 1 (ambient, no-heat) sessions.
Same GroupKFold logic as before, updated feature set: rise-time,
recovery-time, and VOC/NOx ratio replace the old temperature features.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold
from sklearn.metrics import accuracy_score, confusion_matrix

FEATURE_COLS = [
    "delta_bme688_res_ohms",
    "max_delta_bme688_res_ohms",
    "response_bme688_res_ohms_ms",

    "delta_sgp41_sraw_voc",
    "max_delta_sgp41_sraw_voc",
    "response_sgp41_sraw_voc_ms",

    "delta_sgp41_sraw_nox",
    "max_delta_sgp41_sraw_nox",
    "response_sgp41_sraw_nox_ms",

    "voc_nox_ratio",
]


def train_and_evaluate(feature_df: pd.DataFrame, n_splits: int = 5):
    X = feature_df[FEATURE_COLS]
    y = feature_df["label"]
    groups = feature_df["session_id"]

    n_splits = min(n_splits, groups.nunique())
    gkf = GroupKFold(n_splits=n_splits)

    fold_accuracies = []
    importance_sum = np.zeros(len(FEATURE_COLS))

    for fold, (train_idx, test_idx) in enumerate(gkf.split(X, y, groups), start=1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        clf.fit(X_train, y_train)
        preds = clf.predict(X_test)

        acc = accuracy_score(y_test, preds)
        fold_accuracies.append(acc)
        importance_sum += clf.feature_importances_

        held_out = sorted(groups.iloc[test_idx].unique())
        print(f"Fold {fold}/{n_splits}  (held-out sessions: {held_out})")
        print(f"  Accuracy: {acc:.3f}")
        print(f"  Confusion matrix [[TN FP] [FN TP]]:\n{confusion_matrix(y_test, preds)}")

    print("\n=== Summary ===")
    print(f"Mean accuracy across {n_splits} folds: "
    f"{np.mean(fold_accuracies):.3f} (+/- {np.std(fold_accuracies):.3f})")

    importances = pd.Series(
        importance_sum / n_splits, index=FEATURE_COLS
    ).sort_values(ascending=False)
    print("\nAverage feature importances:")
    print(importances.round(3).to_string())

    # break down accuracy per compound too, not just per binary label,
    # useful today since your "positive" class spans 3 unrelated chemicals
    if "compound" in feature_df.columns:
        print("\nPer-compound breakdown (label, count):")
        print(feature_df.groupby(["compound", "label"]).size().to_string())

    final_clf = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    final_clf.fit(X, y)
    return final_clf, importances


if __name__ == "__main__":
    feature_df = pd.read_csv("feature_matrix.csv")
    train_and_evaluate(feature_df)
