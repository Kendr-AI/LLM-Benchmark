"""Build the LLM Benchmark Protocol technical white paper and campaign report.

The renderer intentionally depends only on ReportLab so the publication can be
reproduced in the bundled Codex document runtime.  It supports the Markdown
subset used by the white-paper source: headings, paragraphs, ordered and
unordered lists, pipe tables, fenced code blocks, block quotes, and rules.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Frame,
)
from reportlab.platypus.tableofcontents import TableOfContents


NAVY = HexColor("#11233F")
BLUE = HexColor("#1666D9")
CYAN = HexColor("#20A4B8")
INK = HexColor("#1C2430")
MUTED = HexColor("#596579")
PALE = HexColor("#EDF4FC")
PALE_CYAN = HexColor("#E9F8F8")
LINE = HexColor("#D2DCE9")
AMBER = HexColor("#B26A00")
PALE_AMBER = HexColor("#FFF4DC")
WHITE = colors.white


def _ascii_safe(text: str) -> str:
    """Normalize punctuation that is likely to fail in core PDF fonts."""
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u2265": ">=",
        "\u2264": "<=",
        "\u2248": "~",
        "\u00d7": "x",
        "\u03b1": "alpha",
        "\u03b2": "beta",
        "\u03b4": "delta",
        "\u0394": "Delta",
        "\u03c4": "tau",
        "\u2211": "sum",
        "\u221a": "sqrt",
        "\u2192": "->",
        "\u2194": "<->",
        "\u2022": "*",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _fmt_percent(value: Any, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_number(value: Any, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return "n/a"


def _fmt_usd(value: Any) -> str:
    if value in (None, ""):
        return "n/a"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return "n/a"
    if amount == 0:
        return "$0"
    if abs(amount) < Decimal("0.01"):
        return f"${amount:.5f}"
    return f"${amount:.2f}"


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _campaign_section(
    leaderboard: dict[str, Any],
    audit: dict[str, Any] | None,
    panel_metadata: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    catalog: list[dict[str, Any]] | None,
) -> str:
    results = list(leaderboard.get("results", []))
    failures = list(leaderboard.get("failures", []))
    expected = 0
    if panel_metadata:
        expected = int(
            panel_metadata.get("selected_entries", panel_metadata.get("selected_count", 0)) or 0
        )
    if not expected and manifest:
        expected = len(manifest.get("models", []))
    if not expected:
        expected = len(results) + len(failures)
    complete_count = sum(bool(row.get("complete")) for row in results)
    zero_availability = [
        row for row in results if float(row.get("availability") or 0.0) == 0.0
    ]
    complete_panel = expected > 0 and len(results) == expected and not failures and complete_count == expected
    status = "complete catalog pilot" if complete_panel else "partial catalog pilot"
    created_at = leaderboard.get("created_at", "not recorded")
    sample = (manifest or {}).get("sample_selection", {})
    if not sample and manifest:
        sample = next(
            (value for value in manifest.values() if isinstance(value, dict) and "content_hash" in value),
            {},
        )
    content_hash = (
        leaderboard.get("sample_content_hash")
        or leaderboard.get("content_hash")
        or sample.get("content_hash")
        or "see frozen sample plan"
    )
    qpt = leaderboard.get("questions_per_task", "n/a")
    tasks = list(leaderboard.get("tasks", []))
    questions = max((int(row.get("questions_scored", 0) or 0) for row in results), default=0)
    total_cost = Decimal("0")
    cost_known = True
    lower_bound = False
    for row in results:
        try:
            total_cost += Decimal(str(row.get("cost_usd")))
        except (InvalidOperation, TypeError):
            cost_known = False
        lower_bound = lower_bound or bool(row.get("cost_total_is_lower_bound"))

    catalog_by_id = {
        str(item.get("id")): item for item in (catalog or []) if item.get("id")
    }

    def division(row: dict[str, Any]) -> str:
        model_id = str(row.get("requested_model") or row.get("panel_key") or "")
        item = catalog_by_id.get(model_id, {})
        capabilities = {str(value) for value in item.get("capabilities", [])}
        if item.get("mode") == "intelligent" or model_id in {
            "kendr-intelligent",
            "kendr-research",
            "kendr-flash",
        }:
            return "Routed systems"
        if "deep-research" in model_id or capabilities == {"text", "web_search"}:
            return "Managed research systems"
        return "Fixed managed text endpoints"

    lines = [
        "## 17. Empirical Kendr API catalog campaign",
        "",
        "This section is generated from the frozen machine-readable campaign artifacts. "
        "It is a case study of the KGBP 1.0 reference profile, not evidence of global "
        "acceptance, independent validation, or a full publication-grade study.",
        "",
        "### 17.1 Claim and status",
        "",
        f"Campaign status: **{status}**. The matrix contains {len(results)} finalized endpoint "
        f"records from an expected compatible text panel of {expected}. There were "
        f"{len(failures)} matrix/orchestration failures, while {len(zero_availability)} endpoint "
        "records had zero observed answer availability. Finalization means that the record and "
        "its failure evidence were preserved; it does not mean that the endpoint returned an "
        "answer. Rankings are descriptive for this frozen sample and are not stable universal ranks.",
        "",
        "| Field | Frozen value |",
        "| --- | --- |",
        f"| Matrix ID | {_escape_cell(leaderboard.get('matrix_id', 'n/a'))} |",
        f"| Result generated | {_escape_cell(created_at)} |",
        f"| LiveBench release | {_escape_cell(leaderboard.get('livebench_release', 'n/a'))} |",
        f"| Text endpoints expected / finalized | {expected} / {len(results)} |",
        f"| Finalized records / matrix failures | {complete_count} / {len(failures)} |",
        f"| Zero-availability endpoint records | {len(zero_availability)} |",
        f"| Tasks / questions per task | {len(tasks)} / {qpt} |",
        f"| Questions scored per complete endpoint | {questions} |",
        f"| Frozen content hash | {_escape_cell(content_hash)} |",
        f"| Maximum output tokens | {_escape_cell(leaderboard.get('requested_max_output_tokens', 'n/a'))} |",
        f"| Parallel generation / grading | {_escape_cell(leaderboard.get('parallel_requests', 'n/a'))} / "
        f"{_escape_cell((manifest or {}).get('parallel_grading', 'n/a'))} |",
        f"| Recorded API cost | {_fmt_usd(total_cost) if cost_known else 'partially known'}{' (lower bound)' if lower_bound else ''} |",
        "",
        "The sample uses five LiveBench tasks - data analysis, instruction following, language, "
        "mathematics, and reasoning - with three items per task. Items in this frozen slice date "
        "from 2024. There is one governed generation per item, no multilingual or multimodal track, "
        "no multi-region load phase, no prospective power calculation, and no independent replication. "
        "Accordingly, this campaign fails the KGBP reference-profile freshness, sample-size, repeat, global coverage, "
        "and external-governance publication gates even if its implementation artifacts are complete.",
        "",
        "| Publication evidence gate | KGBP 1.0 reference design | Catalog pilot evidence | Result |",
        "| --- | --- | --- | --- |",
        "| Scored items | 1,200 plus prospective power analysis | 15 | FAIL |",
        "| Independent generations | 5 per stochastic item-system cell | 1 | FAIL |",
        "| Capability tracks | 14 separately reported tracks | 5 narrow task categories | FAIL |",
        "| Language coverage | 15 languages across 8 families | English-language slice | FAIL |",
        "| Freshness | Maximum item age 90 days in reference design | Items dated in 2024 | FAIL |",
        "| Operational load | 5,000 requests per system across 3 regions and load scenarios | 15 task requests; no load phase | FAIL |",
        "| External replication | 2 organizations and at least 3 independent reviewers | None in this pilot | FAIL |",
        "",
        "### 17.2 System-typed descriptive rankings",
        "",
        "The primary ordering is score-weighted operational goodput: objective item score multiplied "
        "by governed answer success, retaining failed and missing calls in the denominator. Quality, "
        "cost completeness, and cumulative final-answer latency are tie-breakers. Confidence intervals "
        "are item-bootstrap intervals; with only 15 items they are expected to be wide. The legacy tier "
        "labels are descriptive overlap groups, not tests of difference or equivalence. Rankings "
        "are primary only within the system-type divisions below. Classification uses the frozen Kendr "
        "catalog's declared mode and capabilities; underlying architecture was not independently verified.",
        "",
    ]
    division_order = (
        "Routed systems",
        "Fixed managed text endpoints",
        "Managed research systems",
    )
    for division_index, division_name in enumerate(division_order, 1):
        division_rows = [row for row in results if division(row) == division_name]
        lines.extend(
            [
                f"#### 17.2.{division_index} {division_name}",
                "",
                "| Div. | Cat. | Endpoint | Goodput | Quality | Avail. | Quality 95% CI | Cost | p50 ms | Tier |",
                "| ---: | ---: | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: |",
            ]
        )
        for division_rank, row in enumerate(division_rows, 1):
            q_low = _fmt_percent(row.get("quality_ci95_low"))
            q_high = _fmt_percent(row.get("quality_ci95_high"))
            lines.append(
                "| {division_rank} | {catalog_rank} | {model} | {goodput} | {quality} | {availability} | {ci} | {cost} | {p50} | {tier} |".format(
                    division_rank=division_rank,
                    catalog_rank=row.get("rank", ""),
                    model=_escape_cell(
                        f"{row.get('model') or row.get('panel_key') or 'unknown'} "
                        f"[{row.get('panel_key') or row.get('requested_model') or 'unversioned'}]"
                    ),
                    goodput=_fmt_percent(row.get("score_weighted_operational_goodput")),
                    quality=_fmt_percent(row.get("quality_score")),
                    availability=_fmt_percent(row.get("availability")),
                    ci=f"{q_low} to {q_high}",
                    cost=_fmt_usd(row.get("cost_usd")) + ("+" if row.get("cost_total_is_lower_bound") else ""),
                    p50=_fmt_number(row.get("latency_p50_ms"), 0),
                    tier=row.get("tier", "n/a"),
                )
            )
        if not division_rows:
            lines.append("| - | - | No completed endpoints in this division | - | - | - | - | - | - | - |")
        lines.append("")

    lines.extend(
        [
            "",
            "### 17.3 Pairwise inference and ranking qualification",
            "",
        ]
    )
    family = leaderboard.get("pairwise_test_family", {})
    pairwise = list(leaderboard.get("pairwise_tests", []))
    significant = [row for row in pairwise if row.get("holm_reject")]
    lines.append(
        f"The frozen family contains {family.get('comparisons', len(pairwise))} paired comparisons. "
        f"The declared test is {family.get('test', 'paired randomization')} with "
        f"{family.get('multiplicity_correction', 'Holm correction')} at alpha = "
        f"{family.get('alpha', 0.05)}. {len(significant)} comparisons reject the corrected null. "
        "A row order finer than supported by these tests is an indexing convenience, not a scientific conclusion."
    )
    lines.extend(
        [
            "",
            "Decision users should first inspect corrected paired effects, practical-equivalence bounds, "
            "track-level scores, reliability, and the cost-quality frontier. A top row alone is insufficient "
            "for procurement, safety assurance, or regulated deployment.",
            "",
            "### 17.4 Routed-system counterfactual analysis",
            "",
        ]
    )
    routing = leaderboard.get("routing_benchmarks") or {}
    if routing.get("available"):
        router = routing.get("router") or {}
        best = routing.get("best_single_endpoint") or {}
        observed = routing.get("observed_selection_counterfactual") or {}
        calibration = routing.get("confidence_calibration") or {}
        lines.extend(
            [
                "The routed-system analysis is a panel counterfactual on objective quality, not a claim "
                "about every destination available to the production router. Regret is reported only when "
                "the selected destination has a standalone, item-matched result in the frozen panel.",
                "",
                "| Router quantity | Estimate | Qualification |",
                "| --- | ---: | --- |",
                f"| Routed-system quality | {_fmt_percent(router.get('score'))} | {_escape_cell(router.get('panel_key', 'router'))} |",
                f"| Best single panel endpoint | {_fmt_percent(best.get('score'))} | {_escape_cell(best.get('model', 'n/a'))} |",
                f"| Uplift over best single | {_fmt_percent(router.get('uplift_over_best_single'))} | Negative means the router underperformed in this sample |",
                f"| Uniform-random endpoint uplift | {_fmt_percent(router.get('uplift_over_random_endpoint'))} | Panel expectation, not production traffic |",
                f"| Panel-oracle score | {_fmt_percent(routing.get('panel_oracle_score'))} | Unattainable item-wise upper envelope |",
                f"| Gap to panel oracle | {_fmt_percent(router.get('gap_to_panel_oracle'))} | Not a regret bound without route coverage |",
                f"| Selected-route counterfactual coverage | {_fmt_percent(observed.get('coverage_of_observed_routes'))} | {observed.get('matched_to_panel_endpoint', 0)} matched routed questions |",
                f"| Confidence Brier score | {_fmt_number(calibration.get('brier_score_against_realized_quality'), 3)} | Realized objective quality, not vendor-defined correctness probability |",
                "",
                f"Regret estimable: **{'yes' if router.get('regret_estimable') else 'no'}**. "
                f"{_escape_cell(router.get('regret_limitation') or routing.get('scope') or '')}",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"No eligible router counterfactual is available: {_escape_cell(routing.get('reason', 'not recorded'))}.",
                "",
            ]
        )
    lines.extend(
        [
            "### 17.5 Failure and applicability register",
            "",
        ]
    )
    if failures:
        lines.extend(["| Matrix target | Orchestration failure |", "| --- | --- |"])
        for failure in failures:
            lines.append(
                f"| {_escape_cell(failure.get('model') or failure.get('panel_key') or 'unknown')} | "
                f"{_escape_cell(failure.get('error') or failure.get('reason') or failure)} |"
            )
    else:
        lines.append(
            "No matrix/orchestration failures are recorded in the leaderboard artifact. This does "
            "not imply full provider availability: finalized zero-score records remain in the denominator."
        )

    if zero_availability:
        lines.extend(
            [
                "",
                "| Zero-availability endpoint | Catalog ID | Observed disposition |",
                "| --- | --- | --- |",
            ]
        )
        for row in zero_availability:
            errors = row.get("provider_error_distribution") or {}
            error_text = ", ".join(
                f"{name}: {count}" for name, count in sorted(errors.items())
            ) or "all planned answers failed; see run artifacts"
            lines.append(
                f"| {_escape_cell(row.get('model') or 'unknown')} | "
                f"{_escape_cell(row.get('panel_key') or row.get('requested_model') or 'unknown')} | "
                f"{_escape_cell(error_text)} |"
            )

    excluded = list(
        (panel_metadata or {}).get("excluded_entries", (panel_metadata or {}).get("excluded", []))
    )
    lines.extend(
        [
            "",
            "Endpoints without text-response applicability are not assigned a zero and are not forced into "
            "the text rank. They require separate modality-specific tracks.",
            "",
            "| Catalog entry | Declared capabilities | Disposition |",
            "| --- | --- | --- |",
        ]
    )
    if excluded:
        for item in excluded:
            capabilities = item.get("capabilities") or item.get("supported_modalities") or item.get("reason") or "non-text"
            if isinstance(capabilities, list):
                capabilities = ", ".join(str(value) for value in capabilities)
            lines.append(
                f"| {_escape_cell(item.get('id') or item.get('model') or item.get('key') or 'unknown')} | "
                f"{_escape_cell(capabilities)} | Separate specialized division |"
            )
    else:
        lines.append("| See catalog snapshot | Non-text or incompatible | Separate specialized division |")

    lines.extend(
        [
            "",
            "### 17.6 Protocol-design audit versus publication evidence",
            "",
        ]
    )
    if audit:
        dimensions = audit.get("dimensions") or audit.get("dimension_scores") or []
        score_values: list[float] = []
        if isinstance(dimensions, dict):
            for value in dimensions.values():
                if isinstance(value, dict):
                    value = value.get("score")
                try:
                    score_values.append(float(value))
                except (TypeError, ValueError):
                    pass
        elif isinstance(dimensions, list):
            for value in dimensions:
                try:
                    score_values.append(float(value.get("score")))
                except (AttributeError, TypeError, ValueError):
                    pass
        minimum = min(score_values) if score_values else audit.get("minimum_dimension_score", "n/a")
        design = audit.get("design_score") or audit.get("geometric_mean") or "n/a"
        lines.append(
            f"The reference configuration records a declaration-completeness score of {design} and a "
            f"minimum dimension score of {minimum}. These values indicate that required design fields "
            "are declared; they do not validate the declarations, measure scientific quality, score the "
            "campaign evidence, or constitute independent assessment. Publication evidence remains blocked."
        )
        if isinstance(dimensions, list) and dimensions:
            lines.extend(
                [
                    "",
                    "| Declared design dimension | Syntax score / 10 | Strict >9 declaration gate |",
                    "| --- | ---: | --- |",
                ]
            )
            for item in dimensions:
                name = str(item.get("dimension", "unknown")).replace("_", " ").title()
                score = item.get("score", "n/a")
                gate = "DECLARED" if item.get("passed") else "INCOMPLETE"
                lines.append(f"| {_escape_cell(name)} | {score} | {gate} |")
    else:
        lines.append(
            "No protocol-audit artifact was supplied to the renderer. The campaign must therefore be "
            "treated as evidence-unverified even if endpoint rows are complete."
        )
    lines.extend(
        [
            "",
            "### 17.7 Required next study",
            "",
            "A publication-grade follow-up should use a preregistered, prospectively powered, multilingual "
            "and multimodal private rolling holdout; at least the configured item and generation floors; "
            "blocked randomization across regions and days; independent human and automated grader audits; "
            "adaptive safety testing; complete cost, energy, and telemetry accounting; and an external "
            "replication performed by an organization that did not build or operate the evaluated systems.",
            "",
        ]
    )
    return "\n".join(lines)


def _inline(text: str) -> str:
    text = _ascii_safe(text.strip())
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a color="#1666D9" href="\2">\1</a>', text)
    return text


def _register_fonts() -> tuple[str, str, str, str]:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/calibri.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/calibrib.ttf"),
    ]
    italic_candidates = [
        Path("C:/Windows/Fonts/ariali.ttf"),
        Path("C:/Windows/Fonts/calibrii.ttf"),
    ]
    bold_italic_candidates = [
        Path("C:/Windows/Fonts/arialbi.ttf"),
        Path("C:/Windows/Fonts/calibriz.ttf"),
    ]
    regular = next((path for path in candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    italic = next((path for path in italic_candidates if path.exists()), None)
    bold_italic = next((path for path in bold_italic_candidates if path.exists()), None)
    if all((regular, bold, italic, bold_italic)):
        pdfmetrics.registerFont(TTFont("KGBP-Regular", str(regular)))
        pdfmetrics.registerFont(TTFont("KGBP-Bold", str(bold)))
        pdfmetrics.registerFont(TTFont("KGBP-Italic", str(italic)))
        pdfmetrics.registerFont(TTFont("KGBP-BoldItalic", str(bold_italic)))
        pdfmetrics.registerFontFamily(
            "KGBP-Regular",
            normal="KGBP-Regular",
            bold="KGBP-Bold",
            italic="KGBP-Italic",
            boldItalic="KGBP-BoldItalic",
        )
        return "KGBP-Regular", "KGBP-Bold", "KGBP-Italic", "KGBP-BoldItalic"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"


def _styles() -> dict[str, ParagraphStyle]:
    regular, bold, italic, _ = _register_fonts()
    samples = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "KGBPTitle", parent=samples["Title"], fontName=bold, fontSize=29, leading=33,
            textColor=WHITE, alignment=TA_LEFT, spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "KGBPSubtitle", parent=samples["Normal"], fontName=regular, fontSize=13.2, leading=18,
            textColor=HexColor("#DCEBFF"), alignment=TA_LEFT,
        ),
        "covermeta": ParagraphStyle(
            "KGBPCoverMeta", parent=samples["Normal"], fontName=regular, fontSize=9.5, leading=14,
            textColor=HexColor("#BDCCE2"),
        ),
        "h1": ParagraphStyle(
            "KGBPH1", parent=samples["Heading1"], fontName=bold, fontSize=18, leading=22,
            textColor=NAVY, spaceBefore=6 * mm, spaceAfter=3.2 * mm, keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "KGBPH2", parent=samples["Heading2"], fontName=bold, fontSize=13.2, leading=17,
            textColor=BLUE, spaceBefore=4.5 * mm, spaceAfter=2.2 * mm, keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "KGBPH3", parent=samples["Heading3"], fontName=bold, fontSize=10.8, leading=14,
            textColor=HexColor("#0B6875"), spaceBefore=3.2 * mm, spaceAfter=1.6 * mm, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "KGBPBody", parent=samples["BodyText"], fontName=regular, fontSize=9.05, leading=13.1,
            textColor=INK, alignment=TA_LEFT, spaceAfter=2.3 * mm, allowWidows=0, allowOrphans=0,
        ),
        "small": ParagraphStyle(
            "KGBPSmall", parent=samples["BodyText"], fontName=regular, fontSize=7.4, leading=9.7,
            textColor=MUTED, spaceAfter=1.5 * mm,
        ),
        "quote": ParagraphStyle(
            "KGBPQuote", parent=samples["BodyText"], fontName=italic, fontSize=8.5, leading=12,
            textColor=MUTED, leftIndent=7 * mm, rightIndent=5 * mm, borderColor=CYAN,
            borderWidth=1.8, borderPadding=(2 * mm, 3 * mm, 2 * mm, 4 * mm),
            backColor=PALE_CYAN, spaceBefore=1.5 * mm, spaceAfter=2.5 * mm,
        ),
        "code": ParagraphStyle(
            "KGBPCode", parent=samples["Code"], fontName="Courier", fontSize=7, leading=9.3,
            textColor=HexColor("#243145"), backColor=HexColor("#F3F6F9"),
            borderColor=LINE, borderWidth=0.5, borderPadding=3 * mm, leftIndent=1 * mm,
            rightIndent=1 * mm, spaceBefore=1.5 * mm, spaceAfter=2.5 * mm,
        ),
        "table": ParagraphStyle(
            "KGBPTable", parent=samples["BodyText"], fontName=regular, fontSize=6.7, leading=8.4,
            textColor=INK,
        ),
        "table_header": ParagraphStyle(
            "KGBPTableHeader", parent=samples["BodyText"], fontName=bold, fontSize=6.8, leading=8.4,
            textColor=WHITE,
        ),
        "toc_h": ParagraphStyle(
            "KGBPTOCHeading", parent=samples["Heading1"], fontName=bold, fontSize=22, leading=26,
            textColor=NAVY, spaceAfter=8 * mm,
        ),
        "toc1": ParagraphStyle(
            "KGBPTOC1", parent=samples["Normal"], fontName=bold, fontSize=9, leading=12,
            textColor=NAVY, leftIndent=0, firstLineIndent=0, spaceBefore=1.2 * mm,
        ),
        "toc2": ParagraphStyle(
            "KGBPTOC2", parent=samples["Normal"], fontName=regular, fontSize=7.8, leading=10,
            textColor=MUTED, leftIndent=5 * mm, firstLineIndent=0,
        ),
    }


class KGBPDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, styles: dict[str, ParagraphStyle], **kwargs: Any) -> None:
        super().__init__(filename, **kwargs)
        self.kgbp_styles = styles
        self._heading_counter = 0

    def beforeDocument(self) -> None:  # noqa: N802 - ReportLab API
        # multiBuild performs multiple passes while resolving the TOC.  Stable
        # bookmark keys are required for convergence.
        self._heading_counter = 0

    def afterFlowable(self, flowable: Flowable) -> None:  # noqa: N802 - ReportLab API
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        # Keep the generated contents usable in a long technical paper. H4
        # headings remain visible in the body but do not expand the TOC into a
        # many-page list of every mathematical subtopic.
        level_map = {"KGBPH1": 0, "KGBPH2": 1}
        if style_name not in level_map:
            return
        level = level_map[style_name]
        title = flowable.getPlainText()
        key = f"heading-{self._heading_counter}"
        self._heading_counter += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, title, self.page, key))


def _cover(canvas: Any, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(BLUE)
    canvas.rect(0, 0, 15 * mm, height, fill=1, stroke=0)
    canvas.setFillColor(CYAN)
    canvas.rect(15 * mm, 0, 2.2 * mm, height, fill=1, stroke=0)
    canvas.setStrokeColor(HexColor("#315477"))
    canvas.setLineWidth(0.5)
    for y in range(24, 285, 18):
        canvas.line(28 * mm, y * mm, 195 * mm, y * mm)
    canvas.restoreState()


def _body_page(canvas: Any, doc: BaseDocTemplate) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 13 * mm, width, 13 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 7.4)
    canvas.setFillColor(WHITE)
    canvas.drawString(18 * mm, height - 8.1 * mm, "LLM BENCHMARK PROTOCOL 1.0  |  KGBP 1.0 REFERENCE PROFILE")
    canvas.setFillColor(CYAN)
    canvas.rect(0, height - 13.8 * mm, width, 0.8 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, width - 18 * mm, 13 * mm)
    canvas.setFont("Helvetica", 7.2)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 8.2 * mm, "Technical proposal - evidence-qualified reporting")
    canvas.drawRightString(width - 18 * mm, 8.2 * mm, f"{doc.page}")
    canvas.restoreState()


def _make_table(rows: list[list[str]], styles: dict[str, ParagraphStyle], available_width: float) -> Table:
    if not rows:
        return Table([[]])
    column_count = max(len(row) for row in rows)
    normalized = [row + [""] * (column_count - len(row)) for row in rows]
    wrapped: list[list[Paragraph]] = []
    for row_index, row in enumerate(normalized):
        style = styles["table_header"] if row_index == 0 else styles["table"]
        wrapped.append([Paragraph(_inline(cell), style) for cell in row])

    header_text = " ".join(normalized[0]).lower()
    if column_count >= 9 and "endpoint" in header_text:
        first = 10 * mm
        second = 10 * mm
        endpoint = 42 * mm
        rest = (available_width - first - second - endpoint) / (column_count - 3)
        widths = [first, second, endpoint] + [rest] * (column_count - 3)
    elif column_count >= 8:
        first = 10 * mm
        second = 36 * mm
        rest = (available_width - first - second) / (column_count - 2)
        widths = [first, second] + [rest] * (column_count - 2)
    elif column_count == 2:
        widths = [available_width * 0.28, available_width * 0.72]
    elif column_count == 3:
        widths = [available_width * 0.25, available_width * 0.39, available_width * 0.36]
    elif column_count == 4:
        widths = [available_width * 0.19, available_width * 0.28, available_width * 0.27, available_width * 0.26]
    else:
        weights = []
        for col in range(column_count):
            max_len = max(len(row[col]) for row in normalized)
            weights.append(min(max(max_len, 7), 34))
        total = sum(weights)
        widths = [available_width * weight / total for weight in weights]

    table = Table(wrapped, colWidths=widths, repeatRows=1, hAlign="LEFT")
    commands: list[tuple[Any, ...]] = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.6 * mm),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, HexColor("#F6F9FC")]),
    ]
    if "rank" in header_text:
        commands.extend(
            [
                ("ALIGN", (0, 1), (0, -1), "RIGHT"),
                ("BACKGROUND", (0, 1), (0, min(3, len(wrapped) - 1)), PALE_AMBER),
                ("TEXTCOLOR", (0, 1), (0, min(3, len(wrapped) - 1)), AMBER),
            ]
        )
    table.setStyle(TableStyle(commands))
    return table


def _ranking_chart(results: list[dict[str, Any]], styles: dict[str, ParagraphStyle]) -> Drawing | None:
    usable = [row for row in results if row.get("score_weighted_operational_goodput") is not None][:12]
    if len(usable) < 2:
        return None
    labels = [str(row.get("model") or row.get("panel_key"))[:31] for row in reversed(usable)]
    values = [float(row["score_weighted_operational_goodput"]) * 100 for row in reversed(usable)]
    drawing = Drawing(470, 210)
    chart = HorizontalBarChart()
    chart.x = 160
    chart.y = 24
    chart.height = 165
    chart.width = 290
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = styles["small"].fontName
    chart.categoryAxis.labels.fontSize = 6.5
    chart.categoryAxis.labels.dx = -4
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(100, (max(values) // 10 + 1) * 10)
    chart.valueAxis.valueStep = 10
    chart.valueAxis.labels.fontSize = 6.5
    chart.valueAxis.labelTextFormat = "%d%%"
    chart.bars[0].fillColor = BLUE
    chart.bars[0].strokeColor = BLUE
    chart.barWidth = 8
    drawing.add(chart)
    drawing.add(String(160, 198, "Catalog goodput index - cross-type, descriptive only", fontName=styles["h3"].fontName, fontSize=9, fillColor=NAVY))
    return drawing


def _parse_table(lines: list[str], start: int) -> tuple[list[list[str]], int]:
    rows: list[list[str]] = []
    index = start
    while index < len(lines) and lines[index].strip().startswith("|"):
        content = lines[index].strip().strip("|")
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", content)]
        if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            rows.append(cells)
        index += 1
    return rows, index


def _markdown_story(
    markdown: str,
    styles: dict[str, ParagraphStyle],
    available_width: float,
    chart: Drawing | None,
) -> list[Flowable]:
    lines = markdown.splitlines()
    story: list[Flowable] = []
    paragraph: list[str] = []
    index = 0
    chart_inserted = False

    def flush_paragraph() -> None:
        if paragraph:
            joined = " ".join(part.strip() for part in paragraph if part.strip())
            if joined:
                story.append(Paragraph(_inline(joined), styles["body"]))
            paragraph.clear()

    while index < len(lines):
        raw = lines[index].rstrip()
        stripped = raw.strip()
        if not stripped:
            flush_paragraph()
            index += 1
            continue
        if stripped.startswith("```"):
            flush_paragraph()
            index += 1
            code_lines: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(_ascii_safe(lines[index]))
                index += 1
            if index < len(lines):
                index += 1
            code = "<br/>".join(html.escape(line) if line else " " for line in code_lines)
            story.append(Paragraph(code, styles["code"]))
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            text = heading.group(2)
            if level == 1:
                # The source H1 and subtitle are represented on the designed cover.
                index += 1
                continue
            if level == 2 and text.startswith("A standards-oriented measurement"):
                index += 1
                continue
            if level == 2:
                story.append(CondPageBreak(28 * mm))
                story.append(Paragraph(_inline(text), styles["h1"]))
            elif level == 3:
                story.append(Paragraph(_inline(text), styles["h2"]))
            else:
                story.append(Paragraph(_inline(text), styles["h3"]))
            if text.startswith("17.2") and chart is not None and not chart_inserted:
                story.append(Spacer(1, 2 * mm))
                story.append(chart)
                story.append(Spacer(1, 1.5 * mm))
                chart_inserted = True
            index += 1
            continue
        if stripped.startswith("|") and index + 1 < len(lines) and lines[index + 1].strip().startswith("|"):
            flush_paragraph()
            rows, index = _parse_table(lines, index)
            story.append(Spacer(1, 1.5 * mm))
            story.append(_make_table(rows, styles, available_width))
            story.append(Spacer(1, 2.5 * mm))
            continue
        if re.match(r"^[-*_]{3,}$", stripped):
            flush_paragraph()
            story.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=2 * mm, spaceAfter=3 * mm))
            index += 1
            continue
        if stripped.startswith(">"):
            flush_paragraph()
            story.append(Paragraph(_inline(stripped.lstrip("> ")), styles["quote"]))
            index += 1
            continue
        list_match = re.match(r"^([-*]|\d+\.)\s+(.+)$", stripped)
        if list_match:
            flush_paragraph()
            ordered = list_match.group(1)[0].isdigit()
            items: list[ListItem] = []
            while index < len(lines):
                current = re.match(r"^\s*([-*]|\d+\.)\s+(.+)$", lines[index])
                if not current or current.group(1)[0].isdigit() != ordered:
                    break
                items.append(ListItem(Paragraph(_inline(current.group(2)), styles["body"]), leftIndent=4 * mm))
                index += 1
            story.append(
                ListFlowable(
                    items,
                    bulletType="1" if ordered else "bullet",
                    start="1",
                    leftIndent=7 * mm,
                    bulletFontName=styles["body"].fontName,
                    bulletFontSize=7.5,
                    bulletColor=BLUE,
                    spaceAfter=1.5 * mm,
                )
            )
            continue
        paragraph.append(stripped)
        index += 1
    flush_paragraph()
    return story


def build_pdf(
    source_path: Path,
    leaderboard_path: Path,
    audit_path: Path | None,
    panel_metadata_path: Path | None,
    manifest_path: Path | None,
    catalog_path: Path | None,
    output_path: Path,
    resolved_path: Path,
) -> None:
    source = source_path.read_text(encoding="utf-8")
    leaderboard = json.loads(leaderboard_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path and audit_path.exists() else None
    metadata = (
        json.loads(panel_metadata_path.read_text(encoding="utf-8"))
        if panel_metadata_path and panel_metadata_path.exists()
        else None
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path and manifest_path.exists() else None
    catalog = json.loads(catalog_path.read_text(encoding="utf-8")) if catalog_path and catalog_path.exists() else None
    section = _campaign_section(leaderboard, audit, metadata, manifest, catalog)
    if "{{CAMPAIGN_RESULTS}}" not in source:
        raise ValueError("White-paper source is missing {{CAMPAIGN_RESULTS}} placeholder")
    resolved = _ascii_safe(source.replace("{{CAMPAIGN_RESULTS}}", section))
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(resolved, encoding="utf-8", newline="\n")

    styles = _styles()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin_left = 18 * mm
    margin_right = 18 * mm
    margin_top = 20 * mm
    margin_bottom = 17 * mm
    available_width = page_width - margin_left - margin_right
    cover_frame = Frame(29 * mm, 28 * mm, page_width - 49 * mm, page_height - 54 * mm, id="cover", showBoundary=0)
    body_frame = Frame(
        margin_left,
        margin_bottom,
        available_width,
        page_height - margin_top - margin_bottom,
        id="body",
        showBoundary=0,
    )
    document = KGBPDocTemplate(
        str(output_path),
        styles,
        pagesize=A4,
        leftMargin=margin_left,
        rightMargin=margin_right,
        topMargin=margin_top,
        bottomMargin=margin_bottom,
        title="LLM Benchmark Protocol 1.0 - KGBP 1.0 Reference Profile",
        author="LLM Benchmark Protocol contributors; reference implementation initiated by Kendr AI",
        subject="Standards-oriented model, endpoint, router, agent, and application evaluation protocol",
        creator="LLM Benchmark Protocol reference publication pipeline",
    )
    document.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[cover_frame], onPage=_cover, autoNextPageTemplate="Body"),
            PageTemplate(id="Body", frames=[body_frame], onPage=_body_page),
        ]
    )

    cover_story: list[Flowable] = [
        Spacer(1, 22 * mm),
        Paragraph("LLM Benchmark<br/>Protocol 1.0", styles["title"]),
        Paragraph(
            "KGBP 1.0 reference profile  |  Technical foundations, normative controls, "
            "and empirical endpoint evaluation",
            styles["subtitle"],
        ),
        Spacer(1, 18 * mm),
        HRFlowable(width="38%", thickness=2.4, color=CYAN, hAlign="LEFT"),
        Spacer(1, 7 * mm),
        Paragraph("TECHNICAL WHITE PAPER", styles["covermeta"]),
        Paragraph("Version 1.0  |  Research release  |  8 August 2026", styles["covermeta"]),
        Paragraph("LLM Benchmark Protocol contributors  |  Reference implementation initiated by Kendr AI", styles["covermeta"]),
        Spacer(1, 24 * mm),
        Paragraph(
            "Status: Public research proposal and reference implementation. The KGBP profile's "
            "automated declaration scores are not independent validation. This document is not an ISO, "
            "NIST, OECD, EU, or MLCommons certification, endorsement, or conformity assessment.",
            styles["covermeta"],
        ),
        PageBreak(),
    ]

    toc = TableOfContents()
    toc.levelStyles = [styles["toc1"], styles["toc2"], styles["toc2"]]
    toc_story: list[Flowable] = [
        Paragraph("Contents", styles["toc_h"]),
        Paragraph(
            "Measurement theory, statistical estimands, experimental design, system-specific evaluation, "
            "evidence assurance, governance, standards status, and a qualified catalog case study.",
            styles["body"],
        ),
        Spacer(1, 3 * mm),
        toc,
        PageBreak(),
    ]
    chart = _ranking_chart(list(leaderboard.get("results", [])), styles)
    body_story = _markdown_story(resolved, styles, available_width, chart)
    story = cover_story + toc_story + body_story
    document.multiBuild(story)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--leaderboard", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--panel-metadata", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resolved-markdown", type=Path, required=True)
    args = parser.parse_args()
    build_pdf(
        args.source.resolve(),
        args.leaderboard.resolve(),
        args.audit.resolve() if args.audit else None,
        args.panel_metadata.resolve() if args.panel_metadata else None,
        args.manifest.resolve() if args.manifest else None,
        args.catalog.resolve() if args.catalog else None,
        args.output.resolve(),
        args.resolved_markdown.resolve(),
    )
    print(json.dumps({
        "output": str(args.output.resolve()),
        "resolved_markdown": str(args.resolved_markdown.resolve()),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
