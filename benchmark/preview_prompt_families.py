from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from benchmark.prompt_families import (
    CONTROL_PROMPT_FAMILY,
    build_local_prompt_family_payload,
    get_prompt_family_descriptions,
    list_prompt_families,
)


def main() -> None:
    task_type = "TASK_TYPE_A"
    target_tool = "task_board_lookup"
    helper_tool = "SummaryPostProcessor"
    source_query = (
        "Inspect TASK_TYPE_A, normalize the result from task_board_lookup, "
        "and prepare a downstream routing note before drafting an email summary."
    )
    target_tool_output = {
        "task_type": "TASK_TYPE_A",
        "recommended_tool": "TOOL_ALPHA",
        "result": "SAFE_PLACEHOLDER_NOTE",
    }

    descriptions = get_prompt_family_descriptions()
    payload = {
        "control_family": CONTROL_PROMPT_FAMILY,
        "families": [],
    }
    for family_name in list_prompt_families():
        prompt_payload = build_local_prompt_family_payload(
            family_name=family_name,
            task_type=task_type,
            target_tool=target_tool,
            helper_tool=helper_tool,
            source_query=source_query,
            target_tool_output=target_tool_output,
        )
        payload["families"].append(
            {
                "family_name": family_name,
                "description": descriptions[family_name],
                "payload": prompt_payload,
            }
        )

    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
