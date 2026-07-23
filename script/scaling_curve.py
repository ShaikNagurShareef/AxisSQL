#!/usr/bin/env python
"""
Inference-scaling experiment for AggAgent.

Sweeps `agg_agent_sampling_budget` over a list of values, runs selection +
predictions JSON + evaluation for each, and produces CSV / JSON / ASCII chart
showing accuracy as a function of compute. Optionally also sweeps over the
verify-loop (Round-2 verification) on/off axis.

Per-budget eval JSONs are kept (tagged), so partial results survive a crash.

Usage:
    uv run script/scaling_curve.py \
        --config config/config-bird-vllm-gemma4.toml \
        --budgets 1,3,8,16,32 \
        --include-pairwise

    # also A/B verify-loop on vs off:
    uv run script/scaling_curve.py --budgets 3,8 --verify-loop both
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import tomlkit


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def write_overridden_config(
    src: Path,
    dst: Path,
    *,
    strategy: str,
    agg_budget: int | None = None,
    filter_top_k: int | None = None,
    shortcut_threshold: float | None = None,
    verify_loop: bool = False,
) -> None:
    doc = tomlkit.loads(src.read_text())
    sel = doc["sql_selection"]
    sel["strategy"] = strategy
    if filter_top_k is not None:
        sel["filter_top_k_sql"] = filter_top_k
    if shortcut_threshold is not None:
        sel["shortcut_consistency_score_threshold"] = shortcut_threshold
    if strategy == "agg_agent":
        sel["agg_agent_mode"] = "both"
        sel["agg_agent_sampling_budget"] = int(agg_budget)
        sel["agg_agent_verify_loop"] = bool(verify_loop)
    dst.write_text(tomlkit.dumps(doc))


def read_selection_save_path(config_path: Path) -> str:
    doc = tomlkit.loads(config_path.read_text())
    return str(doc["sql_selection"]["save_path"])


def clear_selection_snapshot(save_path: str) -> None:
    p = Path(save_path)
    data_dir = Path(f"{save_path}.data")
    if p.exists():
        p.unlink()
    if data_dir.exists():
        shutil.rmtree(data_dir)


def run_subprocess(cmd: list[str], env: dict, label: str) -> None:
    print(f"\n>>> {label}: {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, env=env, cwd=str(PROJECT_ROOT))
    if proc.returncode != 0:
        raise SystemExit(f"[scaling_curve] {label} failed (exit {proc.returncode})")


def run_one_iteration(temp_config: Path, tag: str, save_path: str, base_env: dict) -> dict:
    env = {**base_env, "CONFIG_PATH": str(temp_config)}
    clear_selection_snapshot(save_path)
    run_subprocess(["uv", "run", "runner/run_sql_selection.py"], env, f"[{tag}] selection")
    run_subprocess(["uv", "run", "runner/convert_snapshot_to_sql.py"], env, f"[{tag}] convert")
    eval_output = Path(f"{save_path}.eval.{tag}.json")
    run_subprocess(
        ["uv", "run", "runner/evaluation.py", "--output", str(eval_output)],
        env, f"[{tag}] evaluation",
    )
    return json.loads(eval_output.read_text())


def render_chart(runs: list[dict]) -> str:
    lines = []
    lines.append("=" * 78)
    lines.append("Scaling curve: configuration vs Overall EX")
    lines.append("=" * 78)
    baseline_ex = None
    for run in runs:
        ex = run["metrics"]["overall"]["ex"] or 0.0
        if baseline_ex is None:
            baseline_ex = ex
        delta = (ex - baseline_ex) * 100
        bar = "█" * int(round(50 * ex))
        label = f"{run['label']:<22}"
        lines.append(f"  {label}  {ex*100:6.2f}%  Δ {delta:+6.2f}pp  {bar}")
    lines.append("=" * 78)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/config-bird-vllm-gemma4.toml",
                        help="Source config (default: config/config-bird-vllm-gemma4.toml)")
    parser.add_argument("--budgets", default="1,3,8,16,32",
                        help="Comma-separated agg_agent_sampling_budget values to sweep")
    parser.add_argument("--include-pairwise", action="store_true",
                        help="Also run the original pairwise tournament as a baseline")
    parser.add_argument("--filter-top-k", type=int, default=6,
                        help="filter_top_k_sql override applied to every run (default 6)")
    parser.add_argument("--shortcut-threshold", type=float, default=0.99,
                        help="shortcut_consistency_score_threshold override (default 0.99 - forces AggAgent on most items)")
    parser.add_argument("--verify-loop", choices=["off", "on", "both"], default="off",
                        help="Toggle the Round-2 verify loop: off (single shot), on (always verify), both (run each budget twice for A/B)")
    parser.add_argument("--output-dir", default="results")
    parser.add_argument("--keep-temp-configs", action="store_true",
                        help="Keep per-budget temp config files in config/_scaling_*.toml")
    args = parser.parse_args()

    src_config = (PROJECT_ROOT / args.config).resolve()
    if not src_config.exists():
        sys.exit(f"Config not found: {src_config}")

    save_path = read_selection_save_path(src_config)
    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]

    if args.verify_loop == "off":
        verify_settings = [False]
    elif args.verify_loop == "on":
        verify_settings = [True]
    else:
        verify_settings = [False, True]

    base_env = {**os.environ, "UV_SYSTEM_CERTS": "true"}
    runs: list[dict] = []
    temp_configs: list[Path] = []

    def _do_run(label: str, strategy: str, budget: int | None, verify: bool) -> None:
        tag = label.replace("=", "").replace(" ", "_")
        tmp = PROJECT_ROOT / "config" / f"_scaling_{tag}.toml"
        temp_configs.append(tmp)
        write_overridden_config(
            src_config, tmp,
            strategy=strategy,
            agg_budget=budget,
            filter_top_k=args.filter_top_k,
            shortcut_threshold=args.shortcut_threshold,
            verify_loop=verify,
        )
        print(f"\n--- Running {label} ---", flush=True)
        metrics = run_one_iteration(tmp, tag, save_path, base_env)
        runs.append({
            "label": label,
            "strategy": strategy,
            "agg_agent_sampling_budget": budget,
            "verify_loop": verify if strategy == "agg_agent" else None,
            "metrics": metrics,
        })

    try:
        if args.include_pairwise:
            _do_run("pairwise", "pairwise", None, False)
        for verify in verify_settings:
            tag_suffix = "+verify" if verify else ""
            for b in budgets:
                _do_run(f"agg_b{b}{tag_suffix}", "agg_agent", b, verify)
    finally:
        if not args.keep_temp_configs:
            for tmp in temp_configs:
                if tmp.exists():
                    tmp.unlink()

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "source_config": str(src_config.relative_to(PROJECT_ROOT)),
        "snapshot_path": save_path,
        "filter_top_k_sql": args.filter_top_k,
        "shortcut_consistency_score_threshold": args.shortcut_threshold,
        "verify_loop_setting": args.verify_loop,
        "runs": runs,
    }
    (out_dir / "scaling_curve.json").write_text(json.dumps(summary, indent=2))

    csv_path = out_dir / "scaling_curve.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "label", "strategy", "n_samples", "verify_loop",
            "overall_ex", "simple_ex", "moderate_ex", "challenging_ex",
            "n_evaluable", "n_total",
        ])
        for run in runs:
            m = run["metrics"]
            o = m["overall"]
            by_diff = m.get("by_difficulty", {})

            def _ex(key: str) -> str:
                b = by_diff.get(key, {})
                return f"{b.get('ex'):.4f}" if b.get("ex") is not None else ""

            w.writerow([
                run["label"],
                run["strategy"],
                run["agg_agent_sampling_budget"] if run["agg_agent_sampling_budget"] is not None else "",
                run["verify_loop"] if run["verify_loop"] is not None else "",
                f"{o['ex']:.4f}" if o.get("ex") is not None else "",
                _ex("simple"), _ex("moderate"), _ex("challenging"),
                o["evaluable"], o["total"],
            ])

    print()
    print(render_chart(runs))
    print(f"\nCSV:  {csv_path.relative_to(PROJECT_ROOT)}")
    print(f"JSON: {(out_dir / 'scaling_curve.json').relative_to(PROJECT_ROOT)}")
    print(f"Per-run eval JSONs: {save_path}.eval.<tag>.json")


if __name__ == "__main__":
    main()
