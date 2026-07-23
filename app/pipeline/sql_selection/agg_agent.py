"""
LLM-as-aggregator alternative to the pairwise SQL selection tournament.

Reads ALL top-k candidates (SQL + execution result + consistency score) in one prompt
and asks the LLM for both:
  - <best_index>N</best_index>      : pick the best candidate by 1-based index
  - <synthesized_sql>SQL</synthesized_sql> : an improved SQL combining good parts of multiple candidates

Mode controls how those two outputs are reconciled:
  - "pick":       use the picked candidate; ignore the synthesized SQL
  - "synthesize": always use the synthesized SQL (falls back to picked if it doesn't execute)
  - "both":       use the synthesized SQL if it executes and returns non-None rows; else picked
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.logger import logger
from app.prompt import PromptFactory


def _format_candidates_block(candidates: List[Tuple[str, str, float, float]]) -> str:
    """candidates: [(sql, result_table_str, consistency_score, execution_time)]"""
    chunks = []
    for idx, (sql, result_table_str, consistency, exec_time) in enumerate(candidates, start=1):
        chunks.append(
            f"Candidate {idx} (consistency={consistency:.2f}, execution_time={exec_time:.3f}s):\n"
            f"  SQL:\n{sql.strip()}\n"
            f"  Execution Result:\n{result_table_str.strip()}"
        )
    return "\n\n".join(chunks)


def _parse_agg_agent_response(response: str) -> Optional[Dict[str, Any]]:
    best_idx_match = re.search(r"<best_index>\s*(\d+)\s*</best_index>", response, re.DOTALL)
    synth_match = re.search(r"<synthesized_sql>(.*?)</synthesized_sql>", response, re.DOTALL)
    if not best_idx_match:
        logger.warning("AggAgent: no <best_index> tag in response")
        return None
    best_index = int(best_idx_match.group(1))
    synthesized_sql = synth_match.group(1).strip() if synth_match else None
    if synthesized_sql == "":
        synthesized_sql = None
    return {"best_index": best_index, "synthesized_sql": synthesized_sql}


def _parse_verify_response(response: str) -> Optional[str]:
    final_match = re.search(r"<final_sql>(.*?)</final_sql>", response, re.DOTALL)
    if not final_match:
        logger.warning("AggAgent verify: no <final_sql> tag in response")
        return None
    final_sql = final_match.group(1).strip()
    return final_sql or None


def _round_two_verify(
    *,
    data_item: Any,
    proposed_sql: str,
    llm: Any,
    extractor: Any,
    execution_service: Any,
    database_schema_profile: str,
) -> Tuple[Optional[str], Dict[str, int]]:
    """
    Execute proposed_sql, show its result to the LLM, and ask for OK/REVISED + a final SQL.
    Returns (final_sql or None, token_usage).
    """
    exec_result = execution_service.execute(data_item, proposed_sql)
    if exec_result.result_rows is None:
        proposed_result_str = "(SQL execution failed - result is None)"
    else:
        proposed_result_str = getattr(exec_result, "result_table_str", str(exec_result.result_rows[:20]))

    prompt = PromptFactory.format_agg_agent_verify_prompt(
        database_schema=database_schema_profile,
        question=data_item.question,
        hint=data_item.evidence,
        proposed_sql=proposed_sql,
        proposed_result=proposed_result_str,
    )

    parsed_results, token_usage = extractor.extract_with_retry(
        llm=llm,
        messages=[{"role": "user", "content": prompt}],
        rule_parser=_parse_verify_response,
        fix_end_token=llm.llm_config.fix_end_token,
        end_token="</final_sql>",
        n=1,
    )
    if not parsed_results:
        return None, token_usage
    return parsed_results[0], token_usage


def select_via_agg_agent(
    *,
    data_item: Any,
    top_k_sql_candidates: List[Tuple[str, str, float, float]],
    llm: Any,
    extractor: Any,
    execution_service: Any,
    schema_service: Any,
    sampling_budget: int,
    mode: str,
    verify_loop: bool = False,
) -> Tuple[str, Dict[str, int]]:
    """
    Returns: (final_sql, token_usage_dict).
    """
    assert mode in ("pick", "synthesize", "both"), f"Invalid AggAgent mode: {mode}"
    assert len(top_k_sql_candidates) > 0

    candidates_block = _format_candidates_block(top_k_sql_candidates)
    database_schema_profile = schema_service.build_schema_profile(
        data_item.database_schema_after_schema_linking,
        include_value_statistics=True,
        include_value_examples=True,
    )
    prompt = PromptFactory.format_agg_agent_selection_prompt(
        database_schema=database_schema_profile,
        question=data_item.question,
        hint=data_item.evidence,
        candidates_block=candidates_block,
    )

    total_tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    parsed_results, r1_tokens = extractor.extract_with_retry(
        llm=llm,
        messages=[{"role": "user", "content": prompt}],
        rule_parser=_parse_agg_agent_response,
        fix_end_token=llm.llm_config.fix_end_token,
        end_token="</synthesized_sql>",
        n=sampling_budget,
    )
    for k_ in total_tokens:
        total_tokens[k_] += r1_tokens.get(k_, 0)

    if not parsed_results:
        logger.warning(f"AggAgent: no valid responses for item {data_item.question_id}; falling back to top-1 candidate")
        return top_k_sql_candidates[0][0], total_tokens

    # Majority vote on best_index (clamped to [1, k]).
    k = len(top_k_sql_candidates)
    valid_indices = [r["best_index"] for r in parsed_results if 1 <= r["best_index"] <= k]
    picked_index = Counter(valid_indices).most_common(1)[0][0] if valid_indices else 1
    picked_sql = top_k_sql_candidates[picked_index - 1][0]

    # Pick the synthesized SQL whose execution result is most common among the sampled syntheses.
    synth_candidates = [r["synthesized_sql"] for r in parsed_results if r["synthesized_sql"]]
    chosen_synth: Optional[str] = None
    synth_to_rows_present: Dict[str, bool] = {}
    if synth_candidates:
        synth_to_hash: Dict[str, Optional[str]] = {}
        for s in synth_candidates:
            if s in synth_to_hash:
                continue
            exec_result = execution_service.execute(data_item, s)
            if exec_result.result_rows is None:
                synth_to_hash[s] = None
                synth_to_rows_present[s] = False
                continue
            synth_to_hash[s] = execution_service.hash_result(data_item, exec_result.result_rows)
            synth_to_rows_present[s] = len(exec_result.result_rows) > 0

        executable_synths = [s for s in synth_candidates if synth_to_hash[s] is not None]
        if executable_synths:
            hash_counts = Counter(synth_to_hash[s] for s in executable_synths)
            top_hash, _ = hash_counts.most_common(1)[0]
            for s in executable_synths:
                if synth_to_hash[s] == top_hash:
                    chosen_synth = s
                    break

    # Pick the Round-1 result to send into Round 2 (or to return directly if no verify).
    if mode == "pick":
        round_one_result = picked_sql
    elif mode == "synthesize":
        round_one_result = chosen_synth if chosen_synth is not None else picked_sql
    else:  # "both": prefer synthesized if it executes with non-empty rows
        if chosen_synth is not None and synth_to_rows_present.get(chosen_synth, False):
            round_one_result = chosen_synth
        else:
            round_one_result = picked_sql

    if not verify_loop:
        return round_one_result, total_tokens

    # Round 2: re-examine the Round-1 SQL together with its execution result and emit a final SQL.
    verified_sql, r2_tokens = _round_two_verify(
        data_item=data_item,
        proposed_sql=round_one_result,
        llm=llm,
        extractor=extractor,
        execution_service=execution_service,
        database_schema_profile=database_schema_profile,
    )
    for k_ in total_tokens:
        total_tokens[k_] += r2_tokens.get(k_, 0)

    if verified_sql is None or verified_sql == round_one_result:
        return round_one_result, total_tokens

    # Accept the verifier's revision only if it executes successfully with non-empty rows.
    verified_exec = execution_service.execute(data_item, verified_sql)
    if verified_exec.result_rows is None or len(verified_exec.result_rows) == 0:
        logger.info(f"AggAgent verify: revision didn't execute cleanly for item {data_item.question_id}; keeping Round-1 SQL")
        return round_one_result, total_tokens

    return verified_sql, total_tokens
