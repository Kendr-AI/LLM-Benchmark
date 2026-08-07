from __future__ import annotations

from pathlib import Path

from kendr_bench import livebench_worker


def test_grading_compatibility_patch_skips_empty_jsonl_rows(
    tmp_path: Path,
    monkeypatch,
):
    source = """
if_questions = list(set([m.question for m in old_instruction_following_matches]))
def run():
    judgments = {}
    with open(output_file, "r") as fin:
        for l in fin:
            qid = json.loads(l)["question_id"]
            model = json.loads(l)["model"]
""".lstrip()
    path = tmp_path / "gen_ground_truth_judgment.py"
    path.write_text(source, encoding="utf-8")

    captured: dict[str, str] = {}

    # Code objects do not expose their full source, so intercept compile while
    # leaving execution inert and assert against the text passed into it.
    real_compile = compile

    def recording_compile(text, filename, mode):
        captured["source"] = text
        return real_compile("", filename, mode)

    monkeypatch.setattr("builtins.compile", recording_compile)
    livebench_worker._run_grading_with_compatibility_patch(tmp_path)

    assert "if not l.strip():" in captured["source"]
    assert "m.question['question_id']" in captured["source"]
