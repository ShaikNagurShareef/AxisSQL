#!/bin/bash

# ==============================================================================
# Re-run only SQL Selection + predictions JSON + Evaluation.
# Use this to iterate on selection strategy (e.g. AggAgent) without re-running
# preprocess / vector DB / value retrieval / schema linking / generation / revision.
#
# Usage:
#   bash script/run_selection_eval.sh config/your_config.toml
# ==============================================================================

PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

if [ ! -z "$1" ]; then
    export CONFIG_PATH="$1"
fi
if [ -z "$CONFIG_PATH" ]; then
    export CONFIG_PATH="config/config.toml"
fi

LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/selection_eval_$(date +'%Y%m%d_%H%M%S').log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=============================================================================="
echo "Selection + Evaluation Only"
echo "Config:  $CONFIG_PATH"
echo "Log:     $LOG_FILE"
echo "=============================================================================="

# Clear ONLY the sql_selection snapshot so selection actually re-runs.
# Upstream snapshots (revision and earlier) are kept — they feed the new selection.
SELECTION_PATHS=$(uv run python - <<'PYEOF'
from app.config import get_config
cfg = get_config()
print(cfg.sql_selection_config.save_path)
PYEOF
)

if [ -n "$SELECTION_PATHS" ]; then
    while IFS= read -r p; do
        if [ -e "$p" ] || [ -e "${p}.data" ]; then
            echo "Clearing stale sql_selection snapshot: $p"
            rm -rf "$p" "${p}.data"
        fi
    done <<< "$SELECTION_PATHS"
fi

echo -e "\nStep A: SQL Selection..."
uv run runner/run_sql_selection.py
if [ $? -ne 0 ]; then echo "SQL selection failed!"; exit 1; fi

echo -e "\nStep B: Exporting predictions JSON..."
uv run runner/convert_snapshot_to_sql.py
if [ $? -ne 0 ]; then echo "Predictions export failed!"; exit 1; fi

echo -e "\nStep C: Evaluation..."
uv run runner/evaluation.py
if [ $? -ne 0 ]; then echo "Evaluation failed!"; exit 1; fi

echo -e "\n=============================================================================="
echo "Selection + Evaluation completed."
echo "=============================================================================="
