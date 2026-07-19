from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


def normalize_name(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


@dataclass(frozen=True)
class FighterProfile:
    requested_name: str
    matched_name: str
    matched_side: str
    date: Any
    opponent: str
    stats: dict[str, Any]


class WinnerModelService:
    """Loads the prediction assets once and serves dataset-backed predictions."""

    def __init__(self, model_path: Path, data_path: Path) -> None:
        self.model_path = model_path
        self.data_path = data_path

        bundle = joblib.load(model_path)
        if not isinstance(bundle, dict) or "model" not in bundle:
            raise ValueError(f"Unsupported model bundle: {model_path}")

        self.bundle = bundle
        self.model = bundle["model"]
        self.raw_feature_columns = list(
            bundle.get("raw_feature_columns", bundle.get("feature_columns", []))
        )
        self.model_feature_columns = list(
            bundle.get("model_feature_columns", bundle.get("feature_columns", []))
        )
        self.target_mapping = dict(bundle.get("target_mapping", {"Blue": 0, "Red": 1}))
        self.red_target = self.target_mapping.get("Red", 1)

        saved_preprocessors = bundle.get("preprocessors")
        if saved_preprocessors is None:
            saved_preprocessors = bundle.get("shared_diff_preprocessors")
        if not isinstance(saved_preprocessors, dict):
            raise ValueError("Model bundle does not contain saved preprocessors")

        # Normalize the two bundle formats supported by the notebook.
        self.context_preprocessor = saved_preprocessors.get("context")
        paired = saved_preprocessors.get("paired")
        if paired is None:
            paired = {
                key: value
                for key, value in saved_preprocessors.items()
                if key != "context"
            }
        self.paired_preprocessors = dict(paired)

        self.stats_df = pd.read_csv(data_path)
        if "date" not in self.stats_df.columns:
            raise ValueError("Prediction dataset must contain a date column")
        self.stats_df["date"] = pd.to_datetime(
            self.stats_df["date"], errors="coerce"
        )
        self.stats_df = self.stats_df.sort_values("date").reset_index(drop=True)

        missing_name_columns = {
            "R_fighter",
            "B_fighter",
        } - set(self.stats_df.columns)
        if missing_name_columns:
            raise ValueError(
                f"Prediction dataset is missing columns: {sorted(missing_name_columns)}"
            )

        names = pd.concat(
            [self.stats_df["R_fighter"], self.stats_df["B_fighter"]],
            ignore_index=True,
        ).dropna().astype(str)
        appearance_counts = names.map(normalize_name).value_counts()
        self._fighter_names = sorted(
            name
            for name in names.unique().tolist()
            if appearance_counts.get(normalize_name(name), 0) >= 2
        )
        self._normalized_names = {
            normalize_name(name): name for name in self._fighter_names
        }

    def search_fighters(self, query: str, limit: int = 25) -> list[str]:
        query_norm = normalize_name(query)
        matches = [
            name
            for name in self._fighter_names
            if not query_norm or query_norm in normalize_name(name)
        ]
        return matches[:limit]

    def _matching_fighter_rows(self, fighter_name: str) -> pd.DataFrame:
        query_norm = normalize_name(fighter_name)
        records: list[pd.DataFrame] = []

        for side in ("R", "B"):
            name_column = f"{side}_fighter"
            side_names = self.stats_df[name_column].fillna("").astype(str)
            side_norm = side_names.map(normalize_name)
            exact = side_norm == query_norm
            contains = side_norm.str.contains(query_norm, regex=False, na=False)

            for match_type, mask in (
                ("exact", exact),
                ("contains", contains & ~exact),
            ):
                matches = self.stats_df.loc[mask].copy()
                if matches.empty:
                    continue
                matches["_matched_side"] = side
                matches["_matched_name"] = matches[name_column]
                matches["_match_type"] = match_type
                matches["_match_priority"] = 0 if match_type == "exact" else 1
                records.append(matches)

        if not records:
            return pd.DataFrame()

        return pd.concat(records, ignore_index=True).sort_values(
            ["_match_priority", "date"], ascending=[True, False]
        ).reset_index(drop=True)

    def latest_fighter_profile(self, fighter_name: str) -> FighterProfile:
        matches = self._matching_fighter_rows(fighter_name)
        if matches.empty:
            raise LookupError(f"Fighter not found: {fighter_name}")

        row = matches.iloc[0]
        side = str(row["_matched_side"])
        stats: dict[str, Any] = {}

        for prep in self.paired_preprocessors.values():
            side_column = prep.get(f"{side.lower()}_col") or prep.get(
                f"{side.lower()}_column"
            )
            if not side_column:
                raise ValueError("Paired preprocessor is missing its side columns")
            suffix = side_column[2:]
            stats[suffix] = row[side_column] if side_column in row.index else np.nan

        opponent_column = "B_fighter" if side == "R" else "R_fighter"
        return FighterProfile(
            requested_name=fighter_name,
            matched_name=str(row["_matched_name"]),
            matched_side=side,
            date=row["date"],
            opponent=str(row[opponent_column]),
            stats=stats,
        )

    @staticmethod
    def _numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
        if column in frame.columns:
            return pd.to_numeric(frame[column], errors="coerce")
        return pd.Series(np.nan, index=frame.index)

    def _transform_raw_rows(self, raw_rows: list[dict[str, Any]]) -> pd.DataFrame:
        frame = pd.DataFrame(raw_rows)
        output = pd.DataFrame(index=frame.index)

        if self.context_preprocessor:
            context_columns = self.context_preprocessor["columns"]
            for column in context_columns:
                if column not in frame.columns:
                    frame[column] = np.nan
            context_values = frame[context_columns].apply(pd.to_numeric, errors="coerce")
            output[context_columns] = self.context_preprocessor["scaler"].transform(
                self.context_preprocessor["imputer"].transform(context_values)
            )

        for key, prep in self.paired_preprocessors.items():
            red_column = prep.get("r_col") or prep.get("r_column")
            blue_column = prep.get("b_col") or prep.get("b_column")
            if not red_column or not blue_column:
                raise ValueError("Paired preprocessor is missing its side columns")

            median = prep["median"]
            red = self._numeric_series(frame, red_column).fillna(median)
            blue = self._numeric_series(frame, blue_column).fillna(median)
            red_scaled = (red - prep["mean"]) / prep["std"]
            blue_scaled = (blue - prep["mean"]) / prep["std"]
            output[f"DIFF_{key}"] = red_scaled - blue_scaled

        return output.reindex(columns=self.model_feature_columns)

    def _build_raw_matchup_row(
        self,
        red_profile: FighterProfile,
        blue_profile: FighterProfile,
        title_bout: bool,
    ) -> dict[str, Any]:
        raw: dict[str, Any] = {column: np.nan for column in self.raw_feature_columns}

        # Context features are not fighter-specific. The saved context scaler
        # defines the exact columns that must be supplied.
        if self.context_preprocessor:
            for column in self.context_preprocessor["columns"]:
                raw[column] = float(bool(title_bout)) if column == "title_bout" else np.nan

        for prep in self.paired_preprocessors.values():
            red_column = prep.get("r_col") or prep.get("r_column")
            blue_column = prep.get("b_col") or prep.get("b_column")
            red_suffix = red_column[2:]
            blue_suffix = blue_column[2:]
            raw[red_column] = red_profile.stats.get(red_suffix, np.nan)
            raw[blue_column] = blue_profile.stats.get(blue_suffix, np.nan)
        return raw

    def _predict_ordered_matchup(
        self, red_fighter: str, blue_fighter: str, title_bout: bool
    ) -> tuple[FighterProfile, FighterProfile, float]:
        red_profile = self.latest_fighter_profile(red_fighter)
        blue_profile = self.latest_fighter_profile(blue_fighter)
        raw_row = self._build_raw_matchup_row(red_profile, blue_profile, title_bout)
        features = self._transform_raw_rows([raw_row])
        probabilities = self.model.predict_proba(features)[0]
        red_index = self._target_index("Red")
        return red_profile, blue_profile, float(probabilities[red_index])

    def _target_index(self, target_name: str) -> int:
        value = self.target_mapping.get(target_name)
        if value is not None:
            return int(value)
        classes = list(getattr(self.model, "classes_", []))
        if target_name == "Red" and 1 in classes:
            return classes.index(1)
        raise ValueError(f"Target mapping does not contain {target_name}")

    def predict(
        self, fighter_a: str, fighter_b: str, title_bout: bool = False
    ) -> dict[str, Any]:
        if normalize_name(fighter_a) == normalize_name(fighter_b):
            raise ValueError("fighter_a and fighter_b must be different fighters")

        a_red, b_blue, a_as_red_probability = self._predict_ordered_matchup(
            fighter_a, fighter_b, title_bout
        )
        b_red, a_blue, b_as_red_probability = self._predict_ordered_matchup(
            fighter_b, fighter_a, title_bout
        )

        fighter_a_probability = (
            a_as_red_probability + (1.0 - b_as_red_probability)
        ) / 2.0
        fighter_b_probability = 1.0 - fighter_a_probability
        predicted_winner = (
            a_red.matched_name
            if fighter_a_probability >= 0.5
            else b_blue.matched_name
        )

        return {
            "fighter_a": a_red.matched_name,
            "fighter_b": b_blue.matched_name,
            "predicted_winner": predicted_winner,
            "fighter_a_probability": round(float(fighter_a_probability), 4),
            "fighter_b_probability": round(float(fighter_b_probability), 4),
        }
