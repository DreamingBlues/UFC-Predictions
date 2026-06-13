import pandas as pd


INPUT_FILE = "ufc-master.csv"
OUTPUT_FILE = "ufc-clean.csv"


def clean_ufc_data(input_file=INPUT_FILE, output_file=OUTPUT_FILE):
    # Load raw dataset
    ufc = pd.read_csv(input_file)

    # Remove duplicate columns if they exist
    ufc = ufc.loc[:, ~ufc.columns.duplicated()].copy()

    # Keep fighter names for clustering and Elo analysis.
    # Keep date because Elo needs chronological fight order.
    # Keep Winner and finish as targets/outcomes.

    columns_to_remove = [
        # Betting odds / market-based columns
        "R_odds",
        "B_odds",
        "R_ev",
        "B_ev",
        "r_dec_odds",
        "b_dec_odds",
        "r_sub_odds",
        "b_sub_odds",
        "r_ko_odds",
        "b_ko_odds",

        # Venue / location columns
        "location",
        "country",
        "empty_arena",

        # Ranking columns
        "B_match_weightclass_rank",
        "R_match_weightclass_rank",
        "R_Women's Flyweight_rank",
        "R_Women's Featherweight_rank",
        "R_Women's Strawweight_rank",
        "R_Women's Bantamweight_rank",
        "R_Heavyweight_rank",
        "R_Light Heavyweight_rank",
        "R_Middleweight_rank",
        "R_Welterweight_rank",
        "R_Lightweight_rank",
        "R_Featherweight_rank",
        "R_Bantamweight_rank",
        "R_Flyweight_rank",
        "R_Pound-for-Pound_rank",
        "B_Women's Flyweight_rank",
        "B_Women's Featherweight_rank",
        "B_Women's Strawweight_rank",
        "B_Women's Bantamweight_rank",
        "B_Heavyweight_rank",
        "B_Light Heavyweight_rank",
        "B_Middleweight_rank",
        "B_Welterweight_rank",
        "B_Lightweight_rank",
        "B_Featherweight_rank",
        "B_Bantamweight_rank",
        "B_Flyweight_rank",
        "B_Pound-for-Pound_rank",
        "better_rank",

        # Existing difference columns
        # These should be rebuilt later in a controlled way as Blue - Red.
        "lose_streak_dif",
        "win_streak_dif",
        "longest_win_streak_dif",
        "win_dif",
        "loss_dif",
        "total_round_dif",
        "total_title_bout_dif",
        "ko_dif",
        "sub_dif",
        "height_dif",
        "reach_dif",
        "age_dif",
        "sig_str_dif",
        "avg_sub_att_dif",
        "avg_td_dif",

    ]

    # Drop irrelevant columns
    ufc = ufc.drop(columns=columns_to_remove, errors="ignore")

    # Combine Blue decision win columns
    blue_decision_cols = [
        "B_win_by_Decision_Majority",
        "B_win_by_Decision_Split",
        "B_win_by_Decision_Unanimous"
    ]

    if all(col in ufc.columns for col in blue_decision_cols):
        ufc["B_win_by_Decision"] = ufc[blue_decision_cols].sum(axis=1)
        ufc = ufc.drop(columns=blue_decision_cols)

    # Combine Red decision win columns
    red_decision_cols = [
        "R_win_by_Decision_Majority",
        "R_win_by_Decision_Split",
        "R_win_by_Decision_Unanimous"
    ]

    if all(col in ufc.columns for col in red_decision_cols):
        ufc["R_win_by_Decision"] = ufc[red_decision_cols].sum(axis=1)
        ufc = ufc.drop(columns=red_decision_cols)

    # Combine Blue KO/TKO columns
    blue_ko_cols = [
        "B_win_by_KO/TKO",
        "B_win_by_TKO_Doctor_Stoppage"
    ]

    if all(col in ufc.columns for col in blue_ko_cols):
        ufc["B_win_by_KO_TKO"] = ufc[blue_ko_cols].sum(axis=1)
        ufc = ufc.drop(columns=blue_ko_cols)

    # Combine Red KO/TKO columns
    red_ko_cols = [
        "R_win_by_KO/TKO",
        "R_win_by_TKO_Doctor_Stoppage"
    ]

    if all(col in ufc.columns for col in red_ko_cols):
        ufc["R_win_by_KO_TKO"] = ufc[red_ko_cols].sum(axis=1)
        ufc = ufc.drop(columns=red_ko_cols)

    # Convert date to datetime, then sort chronologically for Elo analysis
    if "date" in ufc.columns:
        ufc["date"] = pd.to_datetime(ufc["date"], errors="coerce")
        ufc = ufc.sort_values("date").reset_index(drop=True)

    # Keep only fights with valid Red/Blue winners
    if "Winner" in ufc.columns:
        ufc = ufc[ufc["Winner"].isin(["Red", "Blue"])].copy()

    # Drop rows missing essential identifiers/outcomes
    essential_columns = [
        "R_fighter",
        "B_fighter",
        "date",
        "Winner"
    ]

    existing_essential_columns = [
        col for col in essential_columns if col in ufc.columns
    ]

    ufc = ufc.dropna(subset=existing_essential_columns).copy()

    preferred_column_order = [
        # Identifiers / outcomes
        "date",
        "R_fighter",
        "B_fighter",
        "Winner",
        "finish",

        # Fight context
        "title_bout",
        "weight_class",
        "gender",
        "no_of_rounds",

        # Red stats
        "R_current_lose_streak",
        "R_current_win_streak",
        "R_draw",
        "R_avg_SIG_STR_landed",
        "R_avg_SIG_STR_pct",
        "R_avg_SUB_ATT",
        "R_avg_TD_landed",
        "R_avg_TD_pct",
        "R_longest_win_streak",
        "R_losses",
        "R_total_rounds_fought",
        "R_total_title_bouts",
        "R_win_by_Decision",
        "R_win_by_KO_TKO",
        "R_win_by_Submission",
        "R_wins",
        "R_Stance",
        "R_Height_cms",
        "R_Reach_cms",
        "R_Weight_lbs",
        "R_age",

        # Blue stats
        "B_current_lose_streak",
        "B_current_win_streak",
        "B_draw",
        "B_avg_SIG_STR_landed",
        "B_avg_SIG_STR_pct",
        "B_avg_SUB_ATT",
        "B_avg_TD_landed",
        "B_avg_TD_pct",
        "B_longest_win_streak",
        "B_losses",
        "B_total_rounds_fought",
        "B_total_title_bouts",
        "B_win_by_Decision",
        "B_win_by_KO_TKO",
        "B_win_by_Submission",
        "B_wins",
        "B_Stance",
        "B_Height_cms",
        "B_Reach_cms",
        "B_Weight_lbs",
        "B_age"
    ]

    existing_ordered_columns = [
        col for col in preferred_column_order if col in ufc.columns
    ]

    remaining_columns = [
        col for col in ufc.columns if col not in existing_ordered_columns
    ]

    ufc = ufc[existing_ordered_columns + remaining_columns]

    # Save cleaned dataset
    ufc.to_csv(output_file, index=False)

    print(f"Original file: {input_file}")
    print(f"Cleaned file saved as: {output_file}")
    print(f"Rows: {ufc.shape[0]}")
    print(f"Columns: {ufc.shape[1]}")
    print("\nRemaining columns:")
    for col in ufc.columns:
        print(col)

    return ufc


if __name__ == "__main__":
    clean_ufc_data()