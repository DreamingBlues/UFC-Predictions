"""Train one leakage-safe UFC winner model for each betting year.

For a prediction year N, the model is trained only on eligible fights dated before
January 1 of N.  It therefore cannot learn from fight results or fight-level
features from the year being simulated.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


RANDOM_STATE = 99
MIN_PRIOR_FIGHTS = 2
DEFAULT_START_YEAR = 2010
DEFAULT_END_YEAR = 2024

XGB_PARAMS = dict(
    n_estimators=120,
    max_depth=3,
    learning_rate=0.05,
    min_child_weight=3,
    subsample=0.85,
    colsample_bytree=0.85,
    reg_lambda=2.0,
    objective="binary:logistic",
    eval_metric="logloss",
    n_jobs=-1,
)

DROP_PREFIXES = (
    "B_Stance_",
    "R_Stance_",
    "B_Stance",
    "R_Stance",
    "weight_class_",
)
DROP_EXACT = {
    "B_Weight_lbs",
    "R_Weight_lbs",
    "R_prior_fights",
    "B_prior_fights",
}
LEAKAGE_OR_METADATA_COLS = {
    "Winner",
    "winner",
    "winner_side",
    "fight_id",
    "date",
    "R_fighter",
    "B_fighter",
    "win_by",
    "fight_type",
    "R_prior_fights",
    "B_prior_fights",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def keep_feature_col(column: str) -> bool:
    if column in DROP_EXACT or column in LEAKAGE_OR_METADATA_COLS:
        return False
    return not column.startswith(DROP_PREFIXES)


def add_prior_fight_counts(data: pd.DataFrame) -> pd.DataFrame:
    """Add pre-fight appearance counts if the compiled data lacks them."""
    if {"R_prior_fights", "B_prior_fights"}.issubset(data.columns):
        return data

    base = data[["fight_id", "date", "R_fighter", "B_fighter"]].copy()
    red = base.rename(columns={"R_fighter": "fighter"})[["fight_id", "date", "fighter"]]
    red["side"] = "R"
    blue = base.rename(columns={"B_fighter": "fighter"})[["fight_id", "date", "fighter"]]
    blue["side"] = "B"

    appearances = pd.concat([red, blue], ignore_index=True)
    appearances = appearances.sort_values(
        ["fighter", "date", "fight_id", "side"]
    ).reset_index(drop=True)
    appearances["prior_fights"] = appearances.groupby("fighter").cumcount()

    red_counts = (
        appearances[appearances["side"] == "R"]
        [["fight_id", "fighter", "prior_fights"]]
        .rename(columns={"fighter": "R_fighter", "prior_fights": "R_prior_fights"})
    )
    blue_counts = (
        appearances[appearances["side"] == "B"]
        [["fight_id", "fighter", "prior_fights"]]
        .rename(columns={"fighter": "B_fighter", "prior_fights": "B_prior_fights"})
    )

    result = data.merge(red_counts, on=["fight_id", "R_fighter"], how="left")
    return result.merge(blue_counts, on=["fight_id", "B_fighter"], how="left")


def paired_suffixes(columns: list[str]) -> list[str]:
    return sorted(
        {
            column[2:]
            for column in columns
            if column.startswith("R_") and f"B_{column[2:]}" in columns
        }
    )


def mirror_side_rows(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    mirrored = rows.copy()
    for suffix in paired_suffixes(columns):
        red_column, blue_column = f"R_{suffix}", f"B_{suffix}"
        red_values = mirrored[red_column].copy()
        mirrored[red_column] = mirrored[blue_column].to_numpy()
        mirrored[blue_column] = red_values.to_numpy()
    mirrored["Winner"] = mirrored["Winner"].map({"Red": "Blue", "Blue": "Red"})
    return mirrored


def balance_rows(data: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Balance Red/Blue labels by randomly mirroring majority-class rows.

    Mirroring swaps every paired R_/B_ column and inverts the Winner label.
    This also handles a one-class input, which is needed for the early years
    of this dataset where every eligible fight is labeled Red.
    """
    rng = np.random.default_rng(seed)
    balanced = data.copy().reset_index(drop=True)
    counts = balanced["Winner"].value_counts()
    if counts.empty:
        return balanced

    majority = counts.idxmax()
    target_majority = int(np.ceil(counts.sum() / 2))
    rows_to_flip = int(counts[majority] - target_majority)
    if rows_to_flip > 0:
        majority_indices = balanced.index[balanced["Winner"] == majority].to_numpy()
        flip_indices = rng.choice(majority_indices, size=rows_to_flip, replace=False)
        flip_rows = balanced.loc[flip_indices]
        balanced = balanced.drop(index=flip_indices)
        balanced = pd.concat(
            [balanced, mirror_side_rows(flip_rows, list(balanced.columns))],
            ignore_index=True,
        )
    return balanced.reset_index(drop=True)


def make_target(data: pd.DataFrame) -> pd.Series:
    return data["Winner"].map({"Blue": 0, "Red": 1}).astype(int)


def fit_shared_scaled_differences(
    train_data: pd.DataFrame,
    columns: list[str],
) -> tuple[pd.DataFrame, dict]:
    """Fit the notebook's preprocessing and return Red-minus-Blue features."""
    train_out = pd.DataFrame(index=train_data.index)
    preprocessors: dict = {"context": None, "paired": {}}

    context_columns = [
        column for column in columns if not column.startswith(("R_", "B_"))
    ]
    if context_columns:
        imputer = SimpleImputer(strategy="median")
        scaler = StandardScaler()
        train_context = train_data[context_columns].apply(pd.to_numeric, errors="coerce")
        train_imputed = imputer.fit_transform(train_context)
        train_out[context_columns] = scaler.fit_transform(train_imputed)
        preprocessors["context"] = {
            "columns": context_columns,
            "imputer": imputer,
            "scaler": scaler,
        }

    for suffix in paired_suffixes(columns):
        red_column, blue_column = f"R_{suffix}", f"B_{suffix}"
        train_red = pd.to_numeric(train_data[red_column], errors="coerce")
        train_blue = pd.to_numeric(train_data[blue_column], errors="coerce")
        combined = pd.concat([train_red, train_blue], ignore_index=True)
        median = combined.median()
        median = 0.0 if pd.isna(median) else median
        filled = combined.fillna(median)
        mean, std = filled.mean(), filled.std(ddof=0)
        std = 1.0 if pd.isna(std) or std == 0 else std

        train_red_scaled = (train_red.fillna(median) - mean) / std
        train_blue_scaled = (train_blue.fillna(median) - mean) / std
        train_out[f"DIFF_{suffix}"] = train_red_scaled - train_blue_scaled
        preprocessors["paired"][suffix] = {
            "r_column": red_column,
            "b_column": blue_column,
            "median": median,
            "mean": mean,
            "std": std,
        }

    return train_out, preprocessors


def make_xgb_model(seed: int) -> XGBClassifier:
    return XGBClassifier(random_state=seed, **XGB_PARAMS)


def load_eligible_data(data_path: Path) -> tuple[pd.DataFrame, list[str]]:
    data = pd.read_csv(data_path)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = add_prior_fight_counts(data)

    eligible = data[
        data["Winner"].isin(["Red", "Blue"])
        & data["date"].notna()
        & (data["R_prior_fights"] >= MIN_PRIOR_FIGHTS)
        & (data["B_prior_fights"] >= MIN_PRIOR_FIGHTS)
    ].copy().reset_index(drop=True)
    feature_columns = [column for column in eligible.columns if keep_feature_col(column)]
    return eligible, feature_columns


def train_model_for_year(
    eligible_data: pd.DataFrame,
    feature_columns: list[str],
    prediction_year: int,
    model_dir: Path,
    dry_run: bool = False,
) -> dict:
    cutoff = pd.Timestamp(year=prediction_year, month=1, day=1)
    training_data = eligible_data[eligible_data["date"] < cutoff].copy()
    if training_data.empty:
        raise ValueError(f"No eligible training fights before {prediction_year}.")
    if not (training_data["date"] < cutoff).all():
        raise RuntimeError(f"Training data for {prediction_year} contains future fights.")

    # Use a different deterministic sample for each yearly model while keeping
    # runs reproducible.
    balance_seed = RANDOM_STATE + prediction_year
    balanced_data = balance_rows(training_data, balance_seed)
    if balanced_data["Winner"].nunique() != 2:
        raise ValueError(
            f"Training data before {prediction_year} could not be balanced to both classes."
        )
    summary = {
        "prediction_year": prediction_year,
        "training_end_year": prediction_year - 1,
        "training_rows_before_balancing": len(training_data),
        "training_rows": len(balanced_data),
        "red_rows": int((balanced_data["Winner"] == "Red").sum()),
        "blue_rows": int((balanced_data["Winner"] == "Blue").sum()),
        "balance_seed": balance_seed,
    }
    if dry_run:
        return summary

    features, preprocessors = fit_shared_scaled_differences(
        balanced_data, feature_columns
    )
    target = make_target(balanced_data)
    model = make_xgb_model(RANDOM_STATE)
    model.fit(features, target)

    model_path = model_dir / f"xgb_min_for_{prediction_year}.joblib"
    joblib.dump(
        {
            "model": model,
            "preprocessors": preprocessors,
            "raw_feature_columns": feature_columns,
            "model_feature_columns": features.columns.tolist(),
            "target_mapping": {"Blue": 0, "Red": 1},
            "xgb_params": XGB_PARAMS,
            "min_prior_fights": MIN_PRIOR_FIGHTS,
            "balance_seed": balance_seed,
            "prediction_year": prediction_year,
            "training_end_year": prediction_year - 1,
            "training_date_end_exclusive": cutoff.strftime("%Y-%m-%d"),
            "training_rows_before_balancing": len(training_data),
            "training_rows": len(balanced_data),
        },
        model_path,
    )
    summary["model_path"] = str(model_path)
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train one no-future-leakage XGBoost model per prediction year."
    )
    parser.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the year cutoffs and report row counts without writing models.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.end_year < args.start_year:
        raise ValueError("--end-year must be greater than or equal to --start-year.")

    root = project_root()
    data_path = root / "data_clean" / "w_pre_fight_stats.csv"
    model_dir = root / "simulation" / "models"
    eligible_data, feature_columns = load_eligible_data(data_path)

    if not args.dry_run:
        model_dir.mkdir(parents=True, exist_ok=True)

    print(f"Eligible fights: {len(eligible_data)}")
    print(f"Raw feature columns: {len(feature_columns)}")
    for prediction_year in range(args.start_year, args.end_year + 1):
        summary = train_model_for_year(
            eligible_data=eligible_data,
            feature_columns=feature_columns,
            prediction_year=prediction_year,
            model_dir=model_dir,
            dry_run=args.dry_run,
        )
        message = (
            f"{summary['prediction_year']}: trained through {summary['training_end_year']} | "
            f"rows {summary['training_rows_before_balancing']} -> {summary['training_rows']} | "
            f"Red {summary['red_rows']} / Blue {summary['blue_rows']}"
        )
        if "model_path" in summary:
            message += f" | saved {summary['model_path']}"
        print(message)


if __name__ == "__main__":
    main()
