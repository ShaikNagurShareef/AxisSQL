<div align="center">

<h1>AxisSQL</h1>
<p><strong>Mapping the Axes of Inference-Time Scaling for Text-to-SQL</strong></p>

<p>
  <img src="https://img.shields.io/badge/Task-Text--to--SQL-0f766e" alt="Task">
  <img src="https://img.shields.io/badge/Benchmarks-BIRD-7c3aed" alt="Benchmarks">
</p>

<p>
  <img src="https://img.shields.io/badge/Architecture-Multi--Stage%20Pipeline-f97316" alt="Architecture">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white" alt="Python"></a>
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-1f6feb" alt="License"></a>
</p>

<p>
  <a href="#highlights">Highlights</a> ·
  <a href="#results">Results</a> ·
  <a href="#scaling-axes">Scaling Axes</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#evaluation">Evaluation</a> ·
  <a href="#citation">Citation</a>
</p>

</div>

---

<table>
  <tr>
    <td width="52%">
      <h3>What is AxisSQL?</h3>
      <p>
        <strong>AxisSQL</strong> is a controlled measurement study that maps where inference-time compute converts into accuracy 
        in a multi-stage Text-to-SQL pipeline. Rather than optimizing a single design choice, AxisSQL systematically varies 
        five scaling knobs and measures their impact on execution accuracy.
      </p>
      <p>
        Built on the DeepEye-SQL pipeline, AxisSQL identifies the <strong>bottleneck as selection, not sampling</strong>, 
        and demonstrates that an execution-grounded aggregator significantly outperforms traditional voting-based selection.
        Results on <strong>BIRD mini-dev</strong> with four open coder models provide actionable insights for inference scaling.
      </p>
    </td>
    <td width="48%">
      <h3>Key Findings</h3>
      <ul>
        <li><strong>Parallel width saturates early</strong>: sampling more candidates hits diminishing returns</li>
        <li><strong>Selection is the bottleneck</strong>: aggregation beats majority voting and tournaments</li>
        <li><strong>Execution-grounded synthesis</strong>: run-and-verify outperforms pure voting by 4%</li>
        <li><strong>Metadata scales efficiently</strong>: profiling data is cheaper than candidate sampling</li>
        <li><strong>Inference and parameters compose</strong>: test-time compute buys ~one model-size tier</li>
      </ul>
    </td>
  </tr>
</table>

## Highlights

<table>
  <tr>
    <td>📊</td>
    <td><strong>Systematic scaling study</strong> of five inference-time knobs across a fixed pipeline.</td>
  </tr>
  <tr>
    <td>⚙️</td>
    <td><strong>Two primary axes</strong>: parallel width (candidates sampled) and sequential depth (revise/verify rounds).</td>
  </tr>
  <tr>
    <td>🧠</td>
    <td><strong>Execution-grounded aggregation</strong>: run candidates, synthesize from correct fragments, verify results.</td>
  </tr>
  <tr>
    <td>📈</td>
    <td><strong>Practical insights</strong>: selection strategy matters more than pool size on moderate-difficulty queries.</td>
  </tr>
  <tr>
    <td>🛠️</td>
    <td><strong>Four open coder models</strong>: Qwen2.5-Coder-32B, Qwen3-Coder-30B, Gemma-3-27B, Gemma-4-31B.</td>
  </tr>
  <tr>
    <td>📦</td>
    <td><strong>Scaling-curve harness</strong>, per-run outputs, and reproducible configuration suite included.</td>
  </tr>
</table>

## Results

AxisSQL demonstrates significant improvements in execution accuracy on BIRD mini-dev through inference-time scaling.
Execution-grounded aggregation closes the gap between oracle upper bounds and realized accuracy.

| Configuration | Model | EX Accuracy | Improvement | Notes |
| --- | --- | ---: | ---: | --- |
| Baseline (single-shot) | Qwen3-Coder-30B-A3B | 65.8% | — | DeepEye-SQL pipeline |
| Pairwise tournament | Qwen3-Coder-30B-A3B | 69.8% | +4.0pp | Pass@16 with voting |
| Agentic aggregation | Qwen3-Coder-30B-A3B | **73.8%** | **+4.0pp** | Execution-grounded synthesis |
| Moderate-only (agg) | Qwen3-Coder-30B-A3B | **73.2%** | +6.4pp | Gains concentrated here |
| Gemma-4-31B (single) | Gemma-4-31B | 61.2% | — | Baseline 2.6× smaller |
| Gemma-4-9B + scaling | Gemma-4-9B | ~61.2% | Matches | With inference scaling |

## Scaling Axes

AxisSQL studies five scaling knobs that affect inference-time accuracy:

**Primary Axes** (the core 2D plane):
- **Parallel width** ($N$): number of independent SQL candidates sampled per stage
- **Sequential depth** ($R$): number of revise/verify/adjudicate rounds applied to candidates

**Auxiliary Knobs** (reshape the axes):
- **Stage-wise model scaling**: assign stronger models to specific pipeline stages
- **Domain-specific metadata**: profiling and LLM-summarized column metadata
- **Fine-tuning scaling**: task-specific model adaptations

The study reveals that the operating path—from sampling more candidates to realizing accuracy—passes through a competent **agentic aggregator** that executes, compares, and synthesizes SQL queries.

## Built on DeepEye-SQL

AxisSQL is a scaling study of the **DeepEye-SQL** five-stage Text-to-SQL pipeline:

```text
Natural Language Question
        |
        v
1. Value Retrieval (grounding)
2. Schema Linking (relevant context)
3. SQL Generation (diverse candidates)
4. SQL Revision (checker-style repair)
        |
        v
5. SQL Selection ← AxisSQL focuses here
   Parallel width: sample N candidates
   Sequential depth: revise R rounds
   Aggregator: execute, compare, synthesize
```

### Why inference-time scaling matters

- Single-shot generation misses valid alternatives.
- Parallel sampling raises the oracle ceiling but selection is still the bottleneck.
- Execution feedback is underexploited: a run-and-verify aggregator can synthesize new queries from correct fragments.
- Different scaling knobs have asymmetric cost-benefit profiles (metadata is cheap, sampling is expensive).

## Repository Tour

```text
AxisSQL (built on DeepEye-SQL)
├── app/
│   ├── config/          # lazy config loading and typed settings
│   ├── dataset/         # BIRD datasets + structured snapshots
│   ├── db_utils/        # SQL execution, schema loading
│   ├── llm/             # OpenAI-compatible LLM wrapper
│   ├── pipeline/        # five-stage Text-to-SQL pipeline + agg_agent
│   │   └── sql_selection/
│   │       └── agg_agent.py  # execution-grounded aggregation ← AxisSQL contribution
│   ├── services/        # schema service, execution service, artifact store
│   ├── prompt/          # prompt templates
│   └── vector_db/       # vector index creation for value retrieval
├── config/              # model configs (Gemma3/4, Qwen variants) + example configs
├── runner/              # reproducible entry scripts
├── results/             # released predictions and few-shot seeds
├── script/              # helper shell scripts + scaling_curve.py (AxisSQL evaluation)
└── workspace/           # generated snapshots and intermediate outputs
```

### Key entry points

**AxisSQL-specific:**
- [script/scaling_curve.py](script/scaling_curve.py): reproducible scaling study harness (primary experiment script)
- [app/pipeline/sql_selection/agg_agent.py](app/pipeline/sql_selection/agg_agent.py): execution-grounded aggregator (agentic selection)
- [config/config-bird-vllm-gemma\*.toml](config/): model-specific BIRD configurations for four coder models
- [config/config-bird-ngrok-gemma4.toml](config/config-bird-ngrok-gemma4.toml): Gemma-4-31B over an ngrok-tunneled endpoint

**DeepEye-SQL pipeline (foundation):**
- [script/run_pipeline.sh](script/run_pipeline.sh): full pipeline automation
- [runner/preprocess_dataset.py](runner/preprocess_dataset.py): build initial dataset snapshot
- [runner/run_value_retrieval.py](runner/run_value_retrieval.py), [run_schema_linking.py](runner/run_schema_linking.py), [run_sql_generation.py](runner/run_sql_generation.py), [run_sql_revision.py](runner/run_sql_revision.py)
- [runner/run_sql_selection.py](runner/run_sql_selection.py): selection stage (configurable aggregation strategy)
- [runner/evaluation.py](runner/evaluation.py): unified evaluation and scaling analysis

## Installation

### Requirements

- Python `>= 3.12`
- Linux/macOS environment recommended
- OpenAI-compatible LLM endpoint for each stage
- Embedding endpoint or local embedding model for value retrieval

### 1. Clone

```bash
git clone https://github.com/ShaikNagurShareef/AxisSQL.git
cd AxisSQL
```

### 2. Install dependencies

We recommend `uv`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

## Dataset Setup

AxisSQL evaluates on **BIRD mini-dev** (a manageable subset for systematic scaling studies).

### BIRD (required)

Use the provided helper script:

```bash
bash script/download_dataset.sh
```

This downloads the **BIRD dev split**. AxisSQL primarily uses BIRD mini-dev for controlled scaling experiments.

### Configuration notes

- All AxisSQL configs use `root_path = "data/bird/data_minidev/MINIDEV"` by default
- Ensure the BIRD directory structure matches the config paths
- No cloud credentials required for BIRD experiments

## Configuration

AxisSQL includes model-specific BIRD configurations for four open coder models:

- [config/config-bird-vllm-gemma3.toml](config/config-bird-vllm-gemma3.toml) — Gemma-3-27B
- [config/config-bird-vllm-gemma4.toml](config/config-bird-vllm-gemma4.toml) — Gemma-4-31B (internal vLLM host)
- [config/config-bird-ngrok-gemma4.toml](config/config-bird-ngrok-gemma4.toml) — Gemma-4-31B served through an ngrok tunnel (`https://ustllm.ngrok.app/v1`), dev-time testing only
- [config/config-bird-vllm-qwen2.5coder.toml](config/config-bird-vllm-qwen2.5coder.toml) — Qwen2.5-Coder-32B
- [config/config-bird-vllm-qwen3coder.toml](config/config-bird-vllm-qwen3coder.toml) — Qwen3-Coder-30B-A3B
- [config/config-bird-test-gemma.toml](config/config-bird-test-gemma.toml) — Gemma-4-31B, BIRD **test-split** submission config, expects a local vLLM instance (see [Serving Gemma-4-31B for the test submission](#serving-gemma-4-31b-for-the-test-submission))

Legacy example config:
- [config/config-bird-example.toml](config/config-bird-example.toml)

### Important config blocks

#### Dataset

```toml
[dataset]
type = "bird"                # spider | bird | spider2
split = "dev"
root_path = "data/bird"
save_path = "workspace/dataset/bird/dev.snapshot"
```

#### Embedding / vector DB

```toml
[vector_database]
api_type = "openai"          # or local
embedding_model_name_or_path = "your-embedding-model"
store_root_path = "workspace/vector_database/bird/dev"
embedding_device = "auto"       # auto | cpu | cuda | cuda:0
db_parallel = 2
column_parallel = 8
```

#### Stage LLMs

```toml
[sql_generation.llm]
model = "your-model-name"
base_url = "https://your-openai-compatible-endpoint/v1"
api_key = "your-api-key"
max_tokens = 4096
temperature = 0.7
api_type = "openai"
max_model_len = 128000
```

### Selection Strategy (AxisSQL-specific)

The `[sql_selection]` block supports two modes:

```toml
[sql_selection]
# Default: pairwise tournament
strategy = "pairwise"  # classical voting

# AxisSQL mode: execution-grounded aggregation
strategy = "agg_agent"
agg_agent_mode = "both"           # "pick" | "synthesize" | "both"
agg_agent_sampling_budget = 3     # self-consistency samples
agg_agent_max_refine_rounds = 1   # verify-once (0=off, 1=verify, N=multi-round)
agg_agent_decomposition_enabled = false  # question decomposition (future)
```

### Notes

- Each stage can use a different model (configure per `[stage.llm]` block).
- All stage outputs are stored as structured `.snapshot` manifests.
- Only structured `.snapshot` manifests are supported for reproducibility.

## Quick Start

### AxisSQL Scaling Experiment (recommended)

```bash
# Set up the environment
export CONFIG_PATH=config/config-bird-vllm-qwen3coder.toml

# Run the full scaling curve harness
uv run script/scaling_curve.py \
  --config $CONFIG_PATH \
  --model_scale_budget 32000 \
  --selection_strategies pairwise agg_agent \
  --aggregator_modes pick synthesize both
```

### Full Pipeline (single run)

```bash
export CONFIG_PATH=config/config-bird-vllm-qwen3coder.toml
bash script/run_pipeline.sh
```

### Stage-by-Stage

```bash
export CONFIG_PATH=config/config-bird-vllm-qwen3coder.toml

uv run runner/preprocess_dataset.py
uv run runner/create_vector_db_parallel.py
uv run runner/run_value_retrieval.py
uv run runner/run_schema_linking.py
uv run runner/run_sql_generation.py
uv run runner/run_sql_revision.py
uv run runner/run_sql_selection.py  # includes agg_agent if configured
```

### Outputs

- **Dataset snapshot**: `workspace/dataset/bird/dev.snapshot`
- **Stage snapshots**: `workspace/{value_retrieval,schema_linking,sql_generation,sql_revision,sql_selection}/bird/dev.snapshot`
- **Scaling curves** (from `scaling_curve.py`): JSON logs per model and strategy

## Reproducibility

AxisSQL uses **structured snapshots** for checkpoint-and-resume, making long-running scaling studies repeatable.

### Checkpoint workflow

1. **Preprocess**: `uv run runner/preprocess_dataset.py` → creates `workspace/dataset/bird/dev.snapshot`
2. **Vector index**: `uv run runner/create_vector_db_parallel.py` → creates `workspace/vector_database/bird/dev/`
3. **Pipeline**: Run each stage in order; each consumes the previous snapshot and writes a new one
4. **Selection variants**: Re-run `runner/run_sql_selection.py` with different `agg_agent_*` settings without re-running prior stages

### Resume and compare

```bash
# After stage N, you can compare selection strategies on the same candidates:
# - Keep workspace/sql_revision/bird/dev.snapshot
# - Modify [sql_selection] config
# - Re-run: uv run runner/run_sql_selection.py
```

This enables efficient cost-benefit analysis of aggregation strategies without re-running generation and revision.

## Evaluation

AxisSQL evaluates on **BIRD mini-dev** using execution accuracy (EX) as the primary metric.

### Single evaluation run

```bash
uv run runner/evaluation.py \
  --snapshot_path workspace/sql_selection/bird/dev.snapshot \
  --dataset_type bird
```

### Scaling curve analysis

The `scaling_curve.py` harness generates comparative results across:

```bash
uv run script/scaling_curve.py \
  --config config/config-bird-vllm-qwen3coder.toml \
  --model_scale_budget 32000 \
  --selection_strategies pairwise agg_agent \
  --aggregator_modes pick synthesize both \
  --width_values 1 2 4 8 16 32 \
  --depth_values 0 1 2 3
```

### Metrics

- **EX (Execution Accuracy)**: exact match between predicted and gold SQL execution results
- **Pass@N**: oracle upper bound (does at least one of N candidates match gold?)
- **Synthesis gain**: delta between tournament and execution-grounded synthesis
- **Moderate-difficulty focus**: AxisSQL highlights gains concentrated on mid-difficulty queries

## BIRD Bench Test Set Submission

The BIRD Bench **test set** is hidden (`test.json` ships with `"SQL": ""`) and is scored centrally by BIRD's Eval Team.
This section covers everything AxisSQL needs for that submission, per BIRD's official Submission Guideline.

### Which evaluation track applies

All four AxisSQL models (Gemma-3-27B, Gemma-4-31B, Qwen2.5-Coder-32B, Qwen3-Coder-30B-A3B) are ≤34B parameters, so this
is a **Type 1: Single A100 80G GPU Inference** submission — the simplest track (Readme + code + `requirements.txt`,
model push to Hugging Face optional). None of these models are fine-tuned; all are used as their official public
checkpoints, so there is nothing new to upload:

| Model | Hugging Face |
| --- | --- |
| Gemma-3-27B | [google/gemma-3-27b-it](https://huggingface.co/google/gemma-3-27b-it) |
| Gemma-4-31B | [google/gemma-4-31B-it](https://huggingface.co/google/gemma-4-31B-it) |
| Qwen2.5-Coder-32B | [Qwen/Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct) |
| Qwen3-Coder-30B-A3B | [Qwen/Qwen3-Coder-30B-A3B-Instruct](https://huggingface.co/Qwen/Qwen3-Coder-30B-A3B-Instruct) |

### API keys — what's actually needed

- **LLM stage** (`[*.llm]` blocks): for the actual test submission, served by a **local vLLM instance that BIRD's
  Exp Team runs themselves** on their own GPU ([config/config-bird-test-gemma.toml](config/config-bird-test-gemma.toml),
  `http://127.0.0.1:30011/v1` — see [Serving Gemma-4-31B for the test submission](#serving-gemma-4-31b-for-the-test-submission)).
  No real key is needed there either — the `--api-key` you pass to `vllm serve` is whatever you put in the config's
  `api_key` field, and vLLM only checks it matches, so any placeholder string works as long as both sides agree.
  ([config/config-bird-ngrok-gemma4.toml](config/config-bird-ngrok-gemma4.toml) is a separate config used only for
  our own dev-time testing against a tunneled endpoint — not part of the submission.)
- **Embedding stage** (`[vector_database]`): defaults to `api_type = "openai"` (`text-embedding-3-small`), which
  requires a real API key — **provide your own `OPENAI_API_KEY`** (set via env var or directly in the config's
  `api_key` field) for this stage. Per BIRD's guideline, hand it to the Eval Team for their run and
  **reset/rotate it once evaluation completes**.
- **Gemini as an alternative embedding key**: Gemini's OpenAI-compatibility layer also serves embeddings, so it
  works through the exact same `api_type = "openai"` code path with no code changes — just point `base_url` at
  Gemini's compatibility endpoint and use a Gemini API key:
  ```toml
  [vector_database]
  api_type = "openai"
  embedding_model_name_or_path = "gemini-embedding-001"
  base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
  api_key = "your-gemini-api-key-here"
  ```
  (Google's OpenAI-compatibility layer is still in beta as of mid-2026; `gemini-embedding-001` is the text-only
  model — `gemini-embedding-2-preview` is also available if multimodal embeddings are ever needed.)
- A fully key-free option also exists if preferred later: `api_type = "local"` runs embeddings on your own GPU via
  `SentenceTransformerEmbeddingFunction`/`QwenEmbeddingFunction` (`app/vector_db/vector_db.py`), no external key at
  all — not needed here since you're providing OpenAI/Gemini keys directly.

### Compliance notes (per BIRD's guideline)

- **No data exfiltration risk**: SQL execution is a local, read-only `sqlite3` connection
  (`app/db_utils/execution.py`) — the database files themselves are never uploaded or transmitted anywhere. The only
  outbound network calls are the OpenAI-compatible requests to whichever `base_url` you configure per `[*.llm]` /
  `[vector_database]` block (your own model server, or OpenAI if you keep the default embedding config).
- **No reliance on gold SQL**: `gold_sql` is only read in one place outside evaluation —
  `app/pipeline/schema_linking/schema_linking.py`'s `_eval_schema_linking_recall`, a read-only diagnostic metric
  computed *after* schema linking has already made its decisions. It never influences generation, revision, or
  selection, and is explicitly skip-guarded when `gold_sql` is empty (`dataset.py`'s `BirdDataset` maps a missing/blank
  `"SQL"` field to `""`) — i.e. it degrades to a no-op on the real test set.
- **`test_tables.json`**: **not needed.** Schema is introspected directly from each `test_databases/{db_id}/{db_id}.sqlite`
  file (`app/dataset/dataset.py`'s `_load_database_schema`), not from a separate tables manifest.
- **`column_meaning.json`**: **not needed.** AxisSQL doesn't reference this file; it optionally reads BIRD's older
  per-database `database_description/*.csv` files when present (`app/db_utils/schema.py`) and logs a warning and
  continues gracefully when they're absent (verified — this is exactly how the current mini-dev configs already run).
- **Logging & restart-from-error**: every stage writes structured `.snapshot` checkpoints (see
  [Reproducibility](#reproducibility)) that let you resume without re-running prior stages, and
  `script/run_pipeline.sh` tees all stage output to a timestamped file under `logs/`.

### Serving Gemma-4-31B for the test submission

[config/config-bird-test-gemma.toml](config/config-bird-test-gemma.toml) expects a **local** vLLM server on the same
machine that runs the pipeline (i.e. BIRD's Exp Team's own GPU for the Type 1 track — not our ngrok tunnel, which is
only for our own dev-time testing). Before running the pipeline, start vLLM with:

```bash
vllm serve google/gemma-4-31B-it \
  --served-model-name google/gemma-4-31B-it \
  --port 30011 \
  --max-model-len 32768 \
  --api-key your-vllm-api-key-here
```

`--served-model-name` must match the config's `model` field exactly, and `--max-model-len` must match the config's
`max_model_len` (`32768` — the value we've verified actually works with this model; the model card advertises a
much larger native context, so this can be raised if your GPU allocation has headroom, but keep the config's
`max_model_len` in sync with whatever you launch vLLM with). Once vLLM is up and answering on `127.0.0.1:30011`,
proceed with the pipeline below.

### Step-by-step: generating test-set predictions

1. **Request the test set**: email `bird.bench23@gmail.com` with your submission materials and follow BIRD's
   Submission Guideline to receive `test.json` and `test_databases/`.
2. **Place the data**: `data/bird/test/test.json` and `data/bird/test/test_databases/{db_id}/{db_id}.sqlite`.
3. **Create a test-split config**: copy an existing config and switch every `dev` path to `test` — `split`, `root_path`, and every `dev`-named snapshot/storage path (`[dataset].save_path`, `[vector_database].store_root_path`, and each `[*.llm]` stage's sibling `save_path`). All of these follow a `bird/dev...` path convention, so one `sed` pass handles it:

```bash
cp config/config-bird-vllm-qwen3coder.toml config/config-bird-vllm-qwen3coder-test.toml
sed -i.bak \
  -e 's#split = "dev"#split = "test"#' \
  -e 's#root_path = "data/bird/data_minidev/MINIDEV"#root_path = "data/bird"#' \
  -e 's#bird/dev#bird/test#g' \
  config/config-bird-vllm-qwen3coder-test.toml
rm config/config-bird-vllm-qwen3coder-test.toml.bak
export CONFIG_PATH=config/config-bird-vllm-qwen3coder-test.toml
```

`icl_few_shot_examples_path` intentionally keeps pointing at `results/bird_dev_few_shots.json` — those ICL examples come from the labeled dev set regardless of which split you're generating for.

4. **Run the pipeline** exactly as in [Quick Start](#quick-start) (`preprocess_dataset.py` → ... → `run_sql_selection.py`). The test split has no gold SQL, so `runner/evaluation.py` correctly reports "not evaluable" rather than a score — that's expected.
5. **Generate the submission file** in BIRD's official format. With `CONFIG_PATH` still exported from step 3, `--snapshot_path` can be omitted — it's read from `[sql_selection].save_path` in your config:

```bash
uv run runner/convert_snapshot_to_sql.py \
  --dataset_type bird \
  --output results/bird-test/predict_test.json
```

This produces `{question_id: "sql_query\t----- bird -----\tdb_id"}`, the exact format BIRD's evaluation harness expects.

### Submission checklist

Per BIRD's guideline, a Type 1 submission to `bird.bench23@gmail.com` should include:

- [ ] **This README** (submission instructions + commands — already covers setup, config, running the pipeline, and generating predictions).
- [ ] **Code zip** — compressed repo excluding local/generated state:
  ```bash
  zip -r axissql_submission.zip . -x ".git/*" ".venv/*" "workspace/*" "data/*" "*.pyc" "__pycache__/*"
  ```
- [ ] **`requirements.txt`** (already included in this repo, generated via `uv export`) — install with `pip install -r requirements.txt`, or use `uv sync` directly with `pyproject.toml`/`uv.lock`. This package itself has no CUDA-specific pins; CUDA 12.2/12.3 compatibility applies to whatever model-serving stack (e.g. vLLM) you run separately to expose the `[*.llm]` endpoints — verify that against your own serving setup.
- [ ] **Models/keys** — the Hugging Face links above (no custom checkpoints to upload); an `OPENAI_API_KEY` only if you keep OpenAI embeddings instead of switching to local.
- [ ] **`column_meaning.json` usage statement** — not needed (see Compliance notes above).
- [ ] **Dev SQL predictions** — already included at [results/bird-dev/](results/bird-dev/) (`gemma3-27b.json`, `qwen2.5-coder-32b.json`, `qwen3-coder-30b-a3b.json`). These predate the `--dataset_type bird` official-format change and are plain `{question_id: sql}` (no `db_id` suffix); regenerate with `--dataset_type bird` on a dev-split config if BIRD needs the `db_id`-suffixed format for dev too.
- [ ] **`predict_test.json`** generated in step 5 above (or send it once BIRD's Exp Team runs your code, per their workflow).

## Artifacts

### Code and configurations

- **Aggregator**: [app/pipeline/sql_selection/agg_agent.py](app/pipeline/sql_selection/agg_agent.py) — execution-grounded synthesis
- **Scaling harness**: [script/scaling_curve.py](script/scaling_curve.py) — reproducible experiment orchestration
- **Model configs**: [config/config-bird-vllm-\*.toml](config/), [config/config-bird-ngrok-gemma4.toml](config/config-bird-ngrok-gemma4.toml) — Gemma3/4 (vLLM and ngrok), Qwen2.5, Qwen3 configurations

## FAQ

### What is the difference between AxisSQL and DeepEye-SQL?

**DeepEye-SQL** is the five-stage Text-to-SQL pipeline (grounding, linking, generation, revision, selection).
**AxisSQL** is a *scaling study* of DeepEye-SQL that measures where inference-time compute converts to accuracy.
AxisSQL's core contribution is the **agentic aggregator** in the selection stage, which executes, synthesizes, and verifies SQL candidates.

### Can I compare aggregation strategies on the same candidates?

Yes! The snapshot-based workflow lets you:
1. Run stages 1–4 once (value retrieval through revision)
2. Keep the revision snapshot
3. Re-run selection with different `agg_agent_*` configs without re-running generation

### Why focus on BIRD mini-dev?

BIRD mini-dev is a curated 11-database subset of BIRD dev. It's large enough to reveal scaling patterns yet small enough for systematic grid search.
AxisSQL studies a 5D parameter space (width, depth, model scale, metadata, fine-tuning) on a fixed, manageable dataset.

### Can I use local models?

Yes. Any OpenAI-compatible endpoint works. Update the `[*.llm]` blocks in config files with your local server's `base_url` and `api_key`.

## Citation

If you find AxisSQL useful in your research, please cite:

```bibtex
@misc{shareef2026axissql,
  author       = {Shaik Nagur Shareef},
  title        = {{AxisSQL:} Mapping the Axes of Inference-Time Scaling for Text-to-SQL},
  year         = {2026},
  howpublished = {\url{https://github.com/ShaikNagurShareef/AxisSQL}}
}
```

**Built on:**
- [DeepEye-SQL](https://arxiv.org/abs/2510.17586) — the underlying five-stage pipeline
- [BIRD](https://github.com/AlibabaResearch/BIRD) — benchmark for Large-Scale Database Grounded Text-to-SQL

## License

This project is released under the MIT License. See [LICENSE](LICENSE).

## Acknowledgement

AxisSQL builds on **DeepEye-SQL** (the five-stage pipeline) and the **BIRD benchmark**. We thank:
- The BIRD team for curating a challenging and realistic text-to-sql evaluation set
- The DeepEye-SQL authors for the software-engineering-inspired pipeline architecture
- Maintainers of OpenAI-compatible serving frameworks (vLLM, etc.)
- The broader Text-to-SQL research community for benchmarks and baselines
