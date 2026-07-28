from __future__ import annotations

import argparse
import os
import runpy
import sys
from pathlib import Path
from typing import Sequence

from .livebench_adapter import (
    kendr_chat_completion,
    openai_chat_completion,
)

INSTRUCTION_FOLLOWING_COMPATIBILITY_PATCH = (
    "livebench-4355e9b-if-unhashable-question-v1"
)


def _run_grading_with_compatibility_patch(package_dir: Path) -> None:
    """Execute the pinned grader with its unhashable-dict typo corrected.

    Commit 4355e9b constructs ``set([m.question, ...])`` for legacy
    instruction-following questions. Those questions are dictionaries, so the
    official grader crashes before evaluating them. The source checkout stays
    untouched; this exact in-memory replacement only deduplicates by
    ``question_id`` and then executes the pinned module.
    """

    path = package_dir / "gen_ground_truth_judgment.py"
    source = path.read_text(encoding="utf-8")
    needle = (
        "if_questions = list(set([m.question for m in "
        "old_instruction_following_matches]))"
    )
    replacement = (
        "if_questions = list({m.question['question_id']: m.question "
        "for m in old_instruction_following_matches}.values())"
    )
    if needle not in source:
        raise RuntimeError(
            "The pinned LiveBench instruction-following compatibility target "
            "was not found; refusing to patch an unknown grader revision."
        )
    source = source.replace(needle, replacement, 1)
    namespace = {
        "__name__": "__main__",
        "__file__": str(path),
        "__package__": "livebench",
        "__cached__": None,
    }
    exec(compile(source, str(path), "exec"), namespace)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kendr-livebench-worker",
        add_help=False,
    )
    parser.add_argument("--livebench-root", type=Path, required=True)
    parser.add_argument(
        "--adapter",
        choices=("kendr", "openai"),
        default="kendr",
    )
    parser.add_argument(
        "--mode",
        choices=("generation", "grading", "show"),
        default="generation",
    )
    args, livebench_args = parser.parse_known_args(argv)

    root = args.livebench_root.resolve()
    package_dir = root / "livebench"
    if not (package_dir / "gen_api_answer.py").is_file():
        parser.error(f"not a LiveBench source checkout: {root}")

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    sys.path.insert(0, str(root))
    import livebench.common as livebench_common
    import livebench.model as livebench_model

    upstream_get_categories_tasks = livebench_common.get_categories_tasks

    def get_categories_tasks(bench_name: str):
        """Preserve multi-word category names in the pinned LiveBench build.

        The upstream helper applies ``split('_')[0]`` to category path
        components, so ``data_analysis`` and ``instruction_following`` become
        nonexistent Hugging Face datasets named ``data`` and ``instruction``.
        This shim changes only path resolution; questions and graders remain
        the pinned upstream implementations.
        """

        components = bench_name.rstrip("/").split("/")
        if (
            len(components) in (2, 3)
            and components[0] == livebench_common.LIVE_BENCH_DATA_SUPER_PATH
            and components[1] in livebench_common.LIVE_BENCH_CATEGORIES
        ):
            category_name = components[1]
            category = livebench_common.get_hf_dataset(category_name)
            tasks = (
                [components[2]]
                if len(components) == 3
                else livebench_common.get_tasks_from_hf_category(category)
            )
            return {category_name: category}, {category_name: tasks}
        return upstream_get_categories_tasks(bench_name)

    livebench_common.get_categories_tasks = get_categories_tasks
    upstream_get_api_function = livebench_model.get_api_function
    adapter = (
        kendr_chat_completion
        if args.adapter == "kendr"
        else openai_chat_completion
    )

    def get_api_function(provider_name: str, use_litellm: bool = False):
        if provider_name == "local" and not use_litellm:
            return adapter
        return upstream_get_api_function(provider_name, use_litellm)

    # The LiveBench entry modules import these symbols at module load.
    livebench_model.get_api_function = get_api_function
    os.chdir(package_dir)
    modules = {
        "generation": "livebench.gen_api_answer",
        "grading": "livebench.gen_ground_truth_judgment",
        "show": "livebench.show_livebench_result",
    }
    module = modules[args.mode]
    sys.argv = [f"{module.rsplit('.', 1)[-1]}.py", *livebench_args]
    if args.mode == "grading":
        _run_grading_with_compatibility_patch(package_dir)
    else:
        runpy.run_module(module, run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
