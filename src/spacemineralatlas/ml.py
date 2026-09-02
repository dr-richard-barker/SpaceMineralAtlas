"""Machine learning on the plant ionome, sized honestly for the data available.

Sizing the question to the data
-------------------------------
The real dataset is 60 samples with 12 elemental features, split unevenly across
two crops and five missions. That is small. Three consequences shape everything
in this module:

* **No deep or foundation models.** With n=60 there is no regime in which a
  high-capacity model's performance estimate is trustworthy. Regularised linear
  models and a small random forest are the appropriate ceiling.
* **Every model is reported against a baseline.** An accuracy figure alone is
  meaningless at this scale: a stratified dummy classifier on a 29/31 split
  scores near 0.5, and a majority-class dummy scores 0.52, so a model at 0.65 is
  a far weaker result than it sounds. Every reported metric here is accompanied
  by the dummy it must beat.
* **Grouped cross-validation is mandatory.** Samples from one mission share a
  pillow batch, a nutrient charge and a harvest date. A random split would place
  siblings on both sides of the fold boundary and inflate the score. Two grouped
  schemes are used:

  ``LeaveOneMissionOut``
      Holds out one mission at a time -- tests generalisation to a new growout.
  ``LeaveOneCropOut``
      Trains on one crop and tests on the other -- tests whether a flight
      signature transfers across species. This is the harder and more
      scientifically interesting question, and it is the one the earlier Veggie
      analysis claimed to answer without implementing it.

Nested cross-validation is used wherever a hyperparameter is tuned, so the
reported score is never one that a hyperparameter was chosen to maximise.

There are no fallback metrics anywhere in this module. If a model fails to fit,
the exception propagates and the build stops.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .harmonise import ELEMENT_SYMBOLS

logger = logging.getLogger(__name__)

RANDOM_STATE = 42
N_BOOTSTRAP = 2000


def build_models() -> dict[str, tuple[Pipeline, dict]]:
    """Return the candidate models with their hyperparameter grids.

    Both are wrapped in a pipeline with a scaler so that standardisation is
    fitted inside each training fold rather than on the whole dataset, which
    would leak test-fold information into the transform.
    """
    return {
        "logistic_l2": (
            Pipeline([
                ("scale", StandardScaler()),
                ("clf", LogisticRegression(
                    penalty="l2", solver="liblinear", max_iter=5000,
                    class_weight="balanced", random_state=RANDOM_STATE,
                )),
            ]),
            {"clf__C": [0.01, 0.1, 1.0, 10.0]},
        ),
        "random_forest": (
            Pipeline([
                ("scale", StandardScaler()),
                ("clf", RandomForestClassifier(
                    n_estimators=500, class_weight="balanced",
                    random_state=RANDOM_STATE, n_jobs=-1,
                )),
            ]),
            {"clf__max_depth": [2, 3, None], "clf__min_samples_leaf": [1, 2, 4]},
        ),
    }


def _feature_matrix(frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return frame[features].apply(pd.to_numeric, errors="coerce").to_numpy()


def usable_features(frame: pd.DataFrame) -> list[str]:
    """Elements with no missing values across *frame*.

    Imputation is avoided deliberately: missingness here is structural (VEG-03A
    did not assay boron, OSD-745 did not assay aluminium or copper), so an
    imputed value would be an invention rather than a recovery.
    """
    candidates = [c for c in sorted(ELEMENT_SYMBOLS) if c in frame.columns]
    return [
        c for c in candidates
        if pd.to_numeric(frame[c], errors="coerce").notna().all()
    ]


def bootstrap_ci(
    y_true: np.ndarray, y_pred: np.ndarray, *, n: int = N_BOOTSTRAP, alpha: float = 0.05
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval for accuracy."""
    rng = np.random.default_rng(RANDOM_STATE)
    scores = []
    for _ in range(n):
        idx = rng.integers(0, len(y_true), len(y_true))
        if len(np.unique(y_true[idx])) < 1:
            continue
        scores.append(accuracy_score(y_true[idx], y_pred[idx]))
    if not scores:
        return (float("nan"), float("nan"))
    return (
        float(np.percentile(scores, 100 * alpha / 2)),
        float(np.percentile(scores, 100 * (1 - alpha / 2))),
    )


def grouped_evaluation(
    frame: pd.DataFrame,
    features: list[str],
    *,
    group_column: str,
    scheme_name: str,
) -> dict:
    """Evaluate every model under leave-one-group-out CV grouped by *group_column*.

    Hyperparameters are selected by an inner grouped CV on the training folds
    only, so the outer score is an honest estimate.
    """
    X = _feature_matrix(frame, features)
    y = (frame["condition"] == "Flight").astype(int).to_numpy()
    groups = frame[group_column].to_numpy()

    outer = LeaveOneGroupOut()
    n_splits = outer.get_n_splits(X, y, groups)
    logger.info(
        "%s: %d folds over %d samples, %d features",
        scheme_name, n_splits, len(y), len(features),
    )

    results: dict = {
        "scheme": scheme_name,
        "group_column": group_column,
        "n_folds": int(n_splits),
        "n_samples": int(len(y)),
        "n_features": int(len(features)),
        "features": features,
        "class_balance": {"flight": int(y.sum()), "ground": int((1 - y).sum())},
        "models": {},
    }

    # Baselines. Both are evaluated under the identical CV scheme so the
    # comparison is like for like.
    for baseline_name, strategy in (
        ("dummy_stratified", "stratified"), ("dummy_most_frequent", "most_frequent")
    ):
        predictions = np.empty(len(y), dtype=int)
        for train_idx, test_idx in outer.split(X, y, groups):
            dummy = DummyClassifier(strategy=strategy, random_state=RANDOM_STATE)
            dummy.fit(X[train_idx], y[train_idx])
            predictions[test_idx] = dummy.predict(X[test_idx])
        low, high = bootstrap_ci(y, predictions)
        results["models"][baseline_name] = {
            "is_baseline": True,
            "accuracy": float(accuracy_score(y, predictions)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
            "accuracy_ci95": [low, high],
        }

    for model_name, (pipeline, grid) in build_models().items():
        predictions = np.empty(len(y), dtype=int)
        probabilities = np.full(len(y), np.nan, dtype=float)
        chosen_params: list[dict] = []

        for train_idx, test_idx in outer.split(X, y, groups):
            inner_groups = groups[train_idx]
            # An inner grouped split needs at least two training groups; with
            # LeaveOneCropOut there is only one, so fall back to the pipeline's
            # defaults rather than tuning on the test fold.
            if len(np.unique(inner_groups)) >= 2:
                search = GridSearchCV(
                    pipeline, grid,
                    cv=LeaveOneGroupOut().split(X[train_idx], y[train_idx], inner_groups),
                    scoring="balanced_accuracy", n_jobs=-1, refit=True,
                )
                search.fit(X[train_idx], y[train_idx])
                estimator = search.best_estimator_
                chosen_params.append(search.best_params_)
            else:
                estimator = pipeline.fit(X[train_idx], y[train_idx])
                chosen_params.append({"note": "defaults; too few groups to tune"})

            predictions[test_idx] = estimator.predict(X[test_idx])
            if hasattr(estimator, "predict_proba"):
                probabilities[test_idx] = estimator.predict_proba(X[test_idx])[:, 1]

        low, high = bootstrap_ci(y, predictions)
        entry = {
            "is_baseline": False,
            "accuracy": float(accuracy_score(y, predictions)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
            "accuracy_ci95": [low, high],
            "hyperparameters_per_fold": chosen_params,
        }
        # AUC needs both classes present and probabilities available.
        if len(np.unique(y)) == 2 and not np.isnan(probabilities).any():
            entry["roc_auc"] = float(roc_auc_score(y, probabilities))
        results["models"][model_name] = entry

    # Report each model's margin over the stronger of the two baselines, since
    # that is the only number that carries information at this sample size.
    best_baseline = max(
        results["models"][b]["balanced_accuracy"]
        for b in ("dummy_stratified", "dummy_most_frequent")
    )
    results["best_baseline_balanced_accuracy"] = float(best_baseline)
    for name, entry in results["models"].items():
        if not entry["is_baseline"]:
            entry["margin_over_baseline"] = float(
                entry["balanced_accuracy"] - best_baseline
            )

    return results


def feature_importance(
    frame: pd.DataFrame, features: list[str], *, group_column: str
) -> pd.DataFrame:
    """Permutation importance from a model fitted on all data.

    Reported as a description of which elements the model leans on, not as
    evidence of biological importance -- with n=60 and correlated features,
    importance ranks are unstable and should be read as indicative only.
    """
    X = _feature_matrix(frame, features)
    y = (frame["condition"] == "Flight").astype(int).to_numpy()

    pipeline, _ = build_models()["random_forest"]
    pipeline.fit(X, y)

    result = permutation_importance(
        pipeline, X, y, n_repeats=50, random_state=RANDOM_STATE,
        scoring="balanced_accuracy", n_jobs=-1,
    )
    return pd.DataFrame({
        "feature": features,
        "importance_mean": result.importances_mean,
        "importance_std": result.importances_std,
    }).sort_values("importance_mean", ascending=False).reset_index(drop=True)
