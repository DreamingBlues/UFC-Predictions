# UFC Predictions Portal: Long-Term Goal and Roadmap

## Product Goal

Build a public UFC analytics and prediction website that:

- Displays the latest and upcoming UFC events.
- Lets users search for fighters and browse fighter data.
- Supports several prediction types.
- Updates event and fight information automatically through scraping.
- Uses manually trained and approved model versions.
- Shows model probabilities, data timestamps, and model metadata.

Potential prediction types include:

- Fight winner
- Method of victory
- Fight duration
- Over or under a selected round total
- Fight reaches decision
- Knockdown or finish-related markets

## Target Architecture

```text
Public users
    |
    v
Next.js frontend
    |
    v
FastAPI backend
    |--------------------|
    v                    v
PostgreSQL           Model registry
    ^                    |
    |                    v
Scheduled scraper    Approved model files
    ^
    |
UFC data sources
```

Model training remains a separate manual workflow:

```text
Updated historical data
    -> preprocessing
    -> candidate model training
    -> evaluation
    -> manual approval
    -> production model activation
```

## Core Technology Stack

- Frontend: Next.js, React, TypeScript
- Backend API: FastAPI
- Database: PostgreSQL
- ORM and migrations: SQLAlchemy plus Alembic, or SQLModel plus Alembic
- Model storage: versioned model files initially; object storage later if needed
- Scraping: existing Python scraper, run as a separate scheduled process
- Local development: Docker Compose
- Production packaging: Docker
- Testing: pytest for backend and Playwright or Vitest for frontend
- CI/CD: GitHub Actions

## Phase 1: Local Fighter Search

Deliver the first vertical feature:

```text
PostgreSQL -> FastAPI -> Next.js fighter autocomplete
```

Outputs:

- `fighters` table
- Fighter import script
- `/fighters/search` endpoint
- Two fighter autocomplete fields

## Phase 2: First Winner Prediction

Refactor the current winner prediction code out of notebooks and into reusable Python modules.

Recommended backend structure:

```text
backend/app/
├── api/
│   ├── fighters.py
│   └── predictions.py
├── services/
│   ├── feature_service.py
│   └── winner_prediction_service.py
├── schemas/
├── database.py
└── main.py
```

Add an endpoint such as:

```text
POST /predictions/winner
```

The response should include:

- Fighter names and IDs
- Predicted winner
- Probability for each fighter
- Model version
- Model training date
- Latest data date used for each fighter
- Warning when fighter history is insufficient

## Phase 3: Event and Fight Data

Add database tables for:

```text
events
fights
fighters
fighter_pre_fight_stats
scrape_runs
```

The frontend should support:

- Latest event page
- Upcoming event page
- Event fight-card view
- Fighter profile pages
- Historical fight results

Suggested API endpoints:

```text
GET /events/latest
GET /events/upcoming
GET /events/{event_id}
GET /fighters/{fighter_id}
GET /fighters/{fighter_id}/fights
```

## Phase 4: Automated Scraping Updates

Keep scraping separate from user requests.

Do not scrape when a visitor opens the website. Instead:

1. A scheduled job runs the scraper.
2. Scraped data is validated.
3. New or changed events and fights are written to PostgreSQL.
4. The website reads the stored data.

Track every scrape run with:

- Start and finish time
- Success or failure
- Events found
- Fights inserted or updated
- Error details

The homepage should show the most recent successfully stored event, not scrape live during page loading.

## Phase 5: Multiple Prediction Models

Create one prediction service per target rather than one large conditional function.

```text
services/
├── winner_service.py
├── method_service.py
├── duration_service.py
└── over_under_service.py
```

Suggested endpoints:

```text
POST /predictions/winner
POST /predictions/method
POST /predictions/duration
POST /predictions/over-under
```

Each endpoint should define its own:

- Required inputs
- Feature list
- Preprocessing pipeline
- Model version
- Output classes or values
- Evaluation metrics

The frontend can expose these through prediction-type dropdowns.

## Phase 6: Model Versioning and Manual Promotion

Store model metadata in a `model_versions` table.

Recommended fields:

```text
id
model_name
version
file_path
trained_at
training_data_end_date
training_rows
metrics_json
feature_schema_version
is_active
```

Manual update process:

1. Update scraped historical data.
2. Run preprocessing.
3. Train candidate models.
4. Evaluate candidates against fixed validation rules.
5. Save the model artifact and metadata.
6. Mark the approved version as active.
7. Reload or restart the prediction service.

Only one version per model type should be active at a time.

## Phase 7: Prediction Caching

Upcoming UFC cards will be viewed repeatedly. Precompute and store predictions for known scheduled fights.

Suggested `predictions` table fields:

```text
fight_id
prediction_type
model_version_id
prediction_json
created_at
```

Benefits:

- Faster page loads
- Consistent results for all users
- Historical record of what the model predicted
- Reduced repeated feature generation

Custom fighter matchups can still be calculated on demand.

## Phase 8: Public Frontend

Main pages:

```text
/
/events
/events/[event-id]
/fighters
/fighters/[fighter-id]
/predict
/models
```

Homepage content:

- Most recent completed event
- Next upcoming event
- Featured fight predictions
- Last data update time
- Active model versions

Prediction page controls:

- Fighter A autocomplete
- Fighter B autocomplete
- Prediction-type dropdown
- Optional title-bout or round-total inputs
- Predict button

Results should clearly distinguish model probabilities from guaranteed outcomes or betting odds.

## Phase 9: Reliability and Security

Before public deployment, add:

- API request validation
- Rate limiting for on-demand predictions
- CORS configuration
- Environment-based secrets
- Database backups
- Structured logging
- Health-check endpoints
- Error monitoring
- Scraper retry handling
- Model-loading failure handling

Recommended health endpoints:

```text
GET /health
GET /health/database
GET /health/models
```

## Phase 10: Testing

Backend tests:

- Fighter search behavior
- Database inserts and updates
- Feature generation
- Prediction response schema
- Model version selection
- Missing-fighter handling

Frontend tests:

- Autocomplete search
- Duplicate-fighter prevention
- Prediction-type selection
- Loading and error states
- Result rendering

Critical model test:

The preprocessing used during live inference must match the preprocessing used during training.

## Phase 11: Deployment

A practical production setup could use:

- Managed PostgreSQL
- Containerized FastAPI service
- Deployed Next.js frontend
- Scheduled scraper container or hosted cron job
- Persistent model storage
- GitHub Actions for tests and deployment

Keep these processes separate:

```text
frontend
backend API
scraper
manual training pipeline
PostgreSQL
```

## Recommended Build Order

1. Local PostgreSQL and fighter search
2. Next.js autocomplete interface
3. Winner prediction endpoint
4. Event and fight database tables
5. Automated scraper-to-database updates
6. Upcoming event and event-card pages
7. Method-of-victory model
8. Duration and over/under models
9. Model registry and manual promotion workflow
10. Prediction caching
11. Testing, monitoring, and rate limiting
12. Public deployment

## Long-Term Completion Criteria

The project reaches its intended goal when:

- Public users can browse events, fighters, and historical data.
- The latest event information updates without manual website editing.
- Users can choose among multiple prediction types.
- Each prediction identifies its active model version and data date.
- Model retraining and production promotion remain controlled manual actions.
- Scraping, serving predictions, and training run as separate workflows.
