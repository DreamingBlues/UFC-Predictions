# fighter_career_stats.csv

`fighter_career_stats.csv` is a fighter-level UFC dataset where each row represents one unique fighter.

The file is created by converting fight-level red/blue corner data into individual fighter-fight rows, then aggregating each fighter's recorded UFC fights into career-level tendency, pace, accuracy, finishing, and defensive metrics.

Most columns are rates, percentages, or per-minute values so fighters with different numbers of fights can be compared more fairly.

## Column Definitions

| Column | Meaning |
|---|---|
| `fighter` | Fighter name. |
| `total_fights` | Number of recorded fights for that fighter. |
| `total_fight_time` | Total cage time across all recorded fights, in seconds. |
| `fight_quickness` | Total fight time divided by total scheduled fight time. Lower values mean fights usually ended earlier. Higher values mean fights usually lasted closer to the full scheduled duration. |
| `win_DEC_pct` | Percentage of wins that came by decision. |
| `win_KO_TKO_pct` | Percentage of wins that came by KO/TKO. |
| `win_SUB_pct` | Percentage of wins that came by submission. |
| `loss_DEC_pct` | Percentage of losses that came by decision. |
| `loss_KO_TKO_pct` | Percentage of losses that came by KO/TKO. |
| `loss_SUB_pct` | Percentage of losses that came by submission. |
| `CTRL_pct` | Percentage of total fight time spent in control position. |
| `SIG_STR_acc` | Career significant strike accuracy: significant strikes landed divided by significant strikes attempted. |
| `TD_acc` | Career takedown accuracy: takedowns landed divided by takedowns attempted. |
| `TOTAL_STR_acc` | Career total strike accuracy: total strikes landed divided by total strikes attempted. |
| `KD_per_min` | Knockdowns per minute. |
| `SUB_ATT_per_min` | Submission attempts per minute. |
| `REV_per_min` | Reversals per minute. |
| `SIG_STR_land_per_min` | Significant strikes landed per minute. |
| `SIG_STR_att_per_min` | Significant strikes attempted per minute. |
| `SIG_STR_absorbed_per_min` | Opponent significant strikes landed against the fighter per minute. |
| `SIG_STR_opp_att_per_min` | Opponent significant strike attempts against the fighter per minute. |
| `SIG_STR_def` | Significant strike defense: percentage of opponent significant strike attempts that did not land. |
| `TOTAL_STR_land_per_min` | Total strikes landed per minute. |
| `TOTAL_STR_att_per_min` | Total strikes attempted per minute. |
| `TOTAL_STR_absorbed_per_min` | Opponent total strikes landed against the fighter per minute. |
| `TOTAL_STR_opp_att_per_min` | Opponent total strike attempts against the fighter per minute. |
| `TOTAL_STR_def` | Total strike defense: percentage of opponent total strike attempts that did not land. |
| `TD_land_per_min` | Takedowns landed per minute. |
| `TD_att_per_min` | Takedowns attempted per minute. |
| `TD_absorbed_per_min` | Opponent takedowns landed against the fighter per minute. |
| `TD_opp_att_per_min` | Opponent takedown attempts against the fighter per minute. |
| `TD_def` | Takedown defense: percentage of opponent takedown attempts that did not land. If opponents attempted zero takedowns, this is left as missing/NaN. |
| `HEAD_land_per_min` | Head strikes landed per minute. |
| `HEAD_att_per_min` | Head strikes attempted per minute. |
| `HEAD_absorbed_per_min` | Opponent head strikes landed against the fighter per minute. |
| `HEAD_opp_att_per_min` | Opponent head strike attempts against the fighter per minute. |
| `BODY_land_per_min` | Body strikes landed per minute. |
| `BODY_att_per_min` | Body strikes attempted per minute. |
| `BODY_absorbed_per_min` | Opponent body strikes landed against the fighter per minute. |
| `BODY_opp_att_per_min` | Opponent body strike attempts against the fighter per minute. |
| `LEG_land_per_min` | Leg strikes landed per minute. |
| `LEG_att_per_min` | Leg strikes attempted per minute. |
| `LEG_absorbed_per_min` | Opponent leg strikes landed against the fighter per minute. |
| `LEG_opp_att_per_min` | Opponent leg strike attempts against the fighter per minute. |
| `DISTANCE_land_per_min` | Distance strikes landed per minute. |
| `DISTANCE_att_per_min` | Distance strikes attempted per minute. |
| `DISTANCE_absorbed_per_min` | Opponent distance strikes landed against the fighter per minute. |
| `DISTANCE_opp_att_per_min` | Opponent distance strike attempts against the fighter per minute. |
| `CLINCH_land_per_min` | Clinch strikes landed per minute. |
| `CLINCH_att_per_min` | Clinch strikes attempted per minute. |
| `CLINCH_absorbed_per_min` | Opponent clinch strikes landed against the fighter per minute. |
| `CLINCH_opp_att_per_min` | Opponent clinch strike attempts against the fighter per minute. |
| `GROUND_land_per_min` | Ground strikes landed per minute. |
| `GROUND_att_per_min` | Ground strikes attempted per minute. |
| `GROUND_absorbed_per_min` | Opponent ground strikes landed against the fighter per minute. |
| `GROUND_opp_att_per_min` | Opponent ground strike attempts against the fighter per minute. |

## Notes

- Percent columns are stored as decimals.
  - Example: `0.65` means `65%`.
- Per-minute columns are calculated using total career fight time.
- Defensive absorbed columns are based on opponent landed stats against the fighter.
- Opponent attempt columns show how much offensive pressure opponents attempted against the fighter.
- `TD_def` may be missing/NaN when a fighter's opponents attempted zero takedowns.