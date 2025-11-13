# Operations Playbook

All operational tasks run the same immediate-mode pipeline. Nothing writes derived files to the repo; every report is regenerated on demand.

## Environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Streamlit UI

```bash
streamlit run app.py
```

- Sidebar sliders feed directly into `run_scenario`.
- The Diagnostics tab (coming in Phase 10) will surface warnings/errors recorded in the ledger.

## Smoke check (local)

Run a quick end-to-end calculation without the UI:

```bash
python - <<'PY'
from src.pipeline import run_scenario
from src.cost_engine import load_cost_database
res = run_scenario(
    inputs={"length": 210, "half_levels_above": 8, "half_levels_below": 1, "num_bays": 2},
    cost_database=load_cost_database(),
    gc_params={"method": "percentage", "value": 9.37},
)
print("OK:", "total=$%0.0f" % res.cost_summary["total"],
      "stalls=%d" % res.garage.total_stalls,
      "$/SF=%0.2f" % res.cost_summary["cost_per_sf"])
PY
```

This validates that the immediate-mode pipeline executes and produces totals.

## Data & References

- `data/cost_database.json` — unit costs and component-specific overrides.
- `data/reference_budget_map.json` — mapping to TechRidge budget categories.
- TechRidge PDFs remain under `data/` for manual reference but are not parsed automatically yet.

## Operational Guardrails

- Never hand-edit generated CSVs/reports; regenerate via the app or the pipeline.
- New analyses should call `run_scenario` directly and record results through the ledger (immediate-mode).
- If you introduce a new invariant, record it in `ScenarioResult.diagnostics` and surface it in both UI and CLI outputs.


