Correct initial launch
Next.js interface
        |
        v
FastAPI
  ├── fighter search
  ├── latest fighter profile lookup
  ├── model preprocessing
  └── probability prediction
        |
        ├── w_pre_fight_stats.csv
        └── xgb_min_final.joblib

PostgreSQL can remain part of the architecture, but it is not the source of model features unless you import the complete latest fighter snapshots into it. A table containing only fighter names cannot support predictions.

Required backend behavior
Startup

FastAPI should load these once when the application starts:

joblib.load("winner/models/xgb_min_final.joblib")
pd.read_csv("data_clean/w_pre_fight_stats.csv")

The joblib bundle already contains:

The trained XGBoost model
Saved imputers and scaling values
Raw feature columns
Final model feature order
Target mapping

That means the API must reuse the saved preprocessing instead of manually rebuilding or approximating features.

Fighter search
GET /fighters/search?q=gamrot

Search unique names from:

R_fighter
B_fighter

in w_pre_fight_stats.csv.

Prediction
POST /predictions/winner

Request:

{
  "fighter_a": "Mateusz Gamrot",
  "fighter_b": "Quillan Salkilld",
  "title_bout": false
}

Response:

{
  "fighter_a": "Mateusz Gamrot",
  "fighter_b": "Quillan Salkilld",
  "predicted_winner": "Quillan Salkilld",
  "fighter_a_probability": 0.2922,
  "fighter_b_probability": 0.7078
}

The existing notebook already performs the correct basic sequence:

Find each fighter’s latest snapshot.
Extract the appropriate red- or blue-side statistics.
Apply the preprocessing saved in the model bundle.
Predict both corner orientations.
Average the two results to reduce red/blue assignment effects.
Revised repository structure
UFC-Predictions/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── routes/
│   │   │   ├── fighters.py
│   │   │   └── predictions.py
│   │   └── services/
│   │       └── winner_model.py
│   └── requirements.txt
├── frontend/
├── data_clean/
│   └── w_pre_fight_stats.csv
├── winner/
│   └── models/
│       └── xgb_min_final.joblib
└── compose.yaml
Correct completion criteria

The initial local launch is complete when:

FastAPI loads xgb_min_final.joblib successfully.
FastAPI loads w_pre_fight_stats.csv.
Fighter autocomplete searches names from the prediction dataset.
Two different fighters can be selected.
The API retrieves both fighters’ latest snapshots.
Saved model preprocessing is applied.
The API returns the predicted winner and both win probabilities.
Next.js displays those probabilities.

One qualification: predict_proba provides the model’s probability-like confidence, but the notebook explicitly notes that it is not necessarily a calibrated betting probability.