"""
UBID Platform — ML Feedback Loop (Module 8)

Trains a logistic regression model on reviewer-labeled pairs.
Weight updates require admin approval before deployment.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

try:
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


FEATURE_ORDER = [
    "pan_match",
    "gstin_match",
    "name_similarity",
    "phonetic_match",
    "pincode_match",
    "address_overlap",
    "director_name_sim",
]

MIN_SAMPLES_TO_TRAIN = 200


def extract_matrix(labeled_pairs: list[dict]):
    """Convert labeled_pairs rows to (X, y) numpy arrays."""
    if not HAS_SKLEARN:
        raise RuntimeError("scikit-learn not installed. Run: pip install scikit-learn numpy")

    X, y = [], []
    for row in labeled_pairs:
        fv = row["feature_vector"]
        X.append([fv.get(f, 0.0) for f in FEATURE_ORDER])
        y.append(int(row["label"]))

    return np.array(X, dtype=float), np.array(y, dtype=int)


def train_model(labeled_pairs: list[dict]) -> Optional[dict]:
    """
    Train logistic regression on labeled pairs.
    Returns a weight dict ready for insertion into ml_model_weights,
    or None if insufficient data.
    """
    if len(labeled_pairs) < MIN_SAMPLES_TO_TRAIN:
        return None

    if not HAS_SKLEARN:
        raise RuntimeError("scikit-learn required for training.")

    X, y = extract_matrix(labeled_pairs)

    model = LogisticRegression(
        solver="lbfgs",
        max_iter=1000,
        C=1.0,
        class_weight="balanced",  # handles imbalanced match/non-match
    )
    model.fit(X, y)

    # Cross-validated precision and recall
    precision_scores = cross_val_score(model, X, y, cv=5, scoring="precision")
    recall_scores    = cross_val_score(model, X, y, cv=5, scoring="recall")

    weights = {
        feature: round(float(coef), 6)
        for feature, coef in zip(FEATURE_ORDER, model.coef_[0])
    }

    # Normalise weights to sum to 1.0 for interpretability
    total = sum(abs(v) for v in weights.values()) or 1.0
    weights_normalised = {k: round(v / total, 6) for k, v in weights.items()}

    return {
        "version":       f"ml-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
        "weights":       weights_normalised,
        "intercept":     round(float(model.intercept_[0]), 6),
        "trained_on":    len(labeled_pairs),
        "precision_val": round(float(precision_scores.mean()), 4),
        "recall_val":    round(float(recall_scores.mean()), 4),
        "status":        "pending_approval",
        "created_at":    datetime.utcnow().isoformat(),
    }
