#!/bin/bash

# ==============================================================================
# DeepEye-SQL General Pipeline Automation Script
# ==============================================================================
# This script runs the full pipeline from preprocessing to SQL selection.
# 
# Usage: 
#   CONFIG_PATH="config/your_config.toml" bash script/run_pipeline.sh
# or
#   bash script/run_pipeline.sh config/your_config.toml
# ==============================================================================

# Set the project root to the directory where the script is located's parent
PROJECT_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$PROJECT_ROOT"

# Set CONFIG_PATH if provided as an argument
if [ ! -z "$1" ]; then
    export CONFIG_PATH="$1"
fi

# Default CONFIG_PATH if not set
if [ -z "$CONFIG_PATH" ]; then
    export CONFIG_PATH="config/config.toml"
fi

# Create logs directory if it doesn't exist
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# Set log file name with timestamp
LOG_FILE="$LOG_DIR/pipeline_$(date +'%Y%m%d_%H%M%S').log"

# Redirect stdout and stderr to both the console and the log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=============================================================================="
echo "Starting the DeepEye-SQL Pipeline..."
echo "Project Root: $PROJECT_ROOT"
echo "Config Path:  $CONFIG_PATH"
echo "Log File:     $LOG_FILE"
echo "=============================================================================="

# 1. Dataset Preprocessing
echo -e "\nStep 1: Dataset Preprocessing..."
uv run runner/preprocess_dataset.py
if [ $? -ne 0 ]; then echo "Preprocessing failed!"; exit 1; fi

# 1b. Stale-snapshot check: downstream stage snapshots whose num_items
# disagrees with the fresh dataset snapshot are leftovers from a previous
# run (e.g. ran with 500 samples, now running with 11). Offer to clear.
echo -e "\nChecking for stale downstream snapshots..."
STALE_PATHS=$(uv run python - <<'PYEOF'
import json
from pathlib import Path
from app.config import get_config

cfg = get_config()
dataset_path = Path(cfg.dataset_config.save_path)
if not dataset_path.exists():
    raise SystemExit(0)
try:
    dataset_n = json.loads(dataset_path.read_text()).get("num_items")
except Exception:
    raise SystemExit(0)

downstream = [
    cfg.value_retrieval_config.save_path,
    cfg.schema_linking_config.save_path,
    cfg.sql_generation_config.save_path,
    cfg.sql_revision_config.save_path,
    cfg.sql_selection_config.save_path,
]
for p in downstream:
    p = Path(p)
    if not p.exists():
        continue
    try:
        n = json.loads(p.read_text()).get("num_items")
    except Exception:
        continue
    if n is not None and dataset_n is not None and n != dataset_n:
        print(str(p))
PYEOF
)

if [ -n "$STALE_PATHS" ]; then
    echo "Stale downstream snapshots (item counts differ from the dataset):"
    echo "$STALE_PATHS" | sed 's/^/  - /'
    read -p "Clear these snapshots and restart downstream stages from scratch? [y/N] " -r STALE_REPLY < /dev/tty
    if [[ "$STALE_REPLY" =~ ^[Yy]$ ]]; then
        while IFS= read -r path; do
            rm -rf "$path" "${path}.data"
            echo "  cleared: $path"
        done <<< "$STALE_PATHS"
    else
        echo "Keeping existing snapshots; downstream stages will operate on stale item sets."
    fi
else
    echo "No stale downstream snapshots detected."
fi

# 2. Create Vector Database
echo -e "\nStep 2: Creating Vector Database (Parallel)..."
uv run runner/create_vector_db_parallel.py
if [ $? -ne 0 ]; then echo "Vector DB creation failed!"; exit 1; fi

# 3. Value Retrieval
echo -e "\nStep 3: Value Retrieval..."
uv run runner/run_value_retrieval.py
if [ $? -ne 0 ]; then echo "Value retrieval failed!"; exit 1; fi

# 4. Schema Linking
echo -e "\nStep 4: Schema Linking..."
uv run runner/run_schema_linking.py
if [ $? -ne 0 ]; then echo "Schema linking failed!"; exit 1; fi

# 5. SQL Generation
echo -e "\nStep 5: SQL Generation..."
uv run runner/run_sql_generation.py
if [ $? -ne 0 ]; then echo "SQL generation failed!"; exit 1; fi

# 6. SQL Revision
echo -e "\nStep 6: SQL Revision..."
uv run runner/run_sql_revision.py
if [ $? -ne 0 ]; then echo "SQL revision failed!"; exit 1; fi

# 7. SQL Selection
echo -e "\nStep 7: SQL Selection..."
uv run runner/run_sql_selection.py
if [ $? -ne 0 ]; then echo "SQL selection failed!"; exit 1; fi

# 8. Export predictions JSON ({question_id: predicted_sql})
echo -e "\nStep 8: Exporting predictions JSON..."
uv run runner/convert_snapshot_to_sql.py
if [ $? -ne 0 ]; then echo "Predictions export failed!"; exit 1; fi

# 9. Evaluation
echo -e "\nStep 9: Evaluation..."
uv run runner/evaluation.py
if [ $? -ne 0 ]; then echo "Evaluation failed!"; exit 1; fi

echo -e "\n=============================================================================="
echo "Pipeline completed successfully!"
echo "=============================================================================="
