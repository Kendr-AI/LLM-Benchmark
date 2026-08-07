# Quickstart

This guide gets a new user from a clean checkout to a zero-cost, failure-aware scorecard. The software is a **research release**. Passing its automated checks does not confer certification, standards conformance, or global acceptance.

## 1. Install from source

Requirements: Git and Python 3.11 or newer.

```bash
git clone https://github.com/Kendr-AI/LLM-Benchmark.git
cd LLM-Benchmark
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install the package and development checks:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
llm-benchmark-protocol --help
```

The optional Kendr integration is installed separately with `python -m pip install -e ".[kendr]"`. It is not needed for this quickstart.

## 2. Run the zero-cost scoring example

The checked-in fixture has six planned schedule cells and five observations. The absent cell must become a zero-scored `missing` observation, demonstrating the complete-denominator rule.

```bash
llm-benchmark-protocol score examples/toy-observations.jsonl \
  --schedule examples/toy-schedule.jsonl \
  --output build/toy-scorecards \
  --bootstrap-samples 500 \
  --seed 7
```

Open:

- `build/toy-scorecards/global-scorecards.md` for the readable track report;
- `build/toy-scorecards/global-scorecards.json` for downstream analysis.

Expected descriptive macro scores are approximately `0.9333` for `alpha` and `0.2333` for `beta`. Do not treat the toy intervals as meaningful: there is only one item per track.

## 3. Audit the reference study design

This command evaluates the configuration structure and the ten non-compensatory design dimensions. It makes no provider calls.

```bash
llm-benchmark-protocol audit config/global-protocol-v1.example.json \
  --output build/reference-audit \
  --strict
```

The example is designed to clear every `>9.0` design gate. It is still only a plan. Do not add `--require-publication-evidence` unless the evidence URIs, reviews, deviations, and replication reports describe a real completed study.

## 4. Estimate a starting sample size

```bash
llm-benchmark-protocol power \
  --minimum-detectable-effect 0.02 \
  --standard-deviation 0.25 \
  --paired-correlation 0.5 \
  --power 0.9 \
  --alpha 0.05
```

This is an approximate planning calculation, not a substitute for pilot-derived cluster and repeat variance or simulation of the preregistered analysis.

## 5. Prepare a real study

Before any paid inference:

1. Copy [`templates/preregistration.md`](../templates/preregistration.md) and state the claim, target population, primary endpoints, exclusions, comparison family, and decision rule.
2. Copy [`templates/system-card.yaml`](../templates/system-card.yaml) for every system boundary being tested.
3. Copy [`config/global-protocol-v1.example.json`](../config/global-protocol-v1.example.json) and replace every illustrative value and evidence URI.
4. Create frozen item descriptors conforming to [`frozen-item-v1.schema.json`](../config/frozen-item-v1.schema.json).
5. Run the strict audit, freeze the configuration and item hashes, then generate the interleaved schedule.

```bash
llm-benchmark-protocol schedule path/to/protocol.json path/to/frozen-items.jsonl \
  --output build/study/schedule.jsonl \
  --seed 20260807 \
  --region asia-south1 \
  --region europe-west1 \
  --region us-east1
```

The command also writes `schedule.jsonl.validation.json`. Execution evidence begins only when an operator records attempts against those immutable schedule IDs.

## 6. Verify the published pilot

The release includes privacy-reviewed aggregate results, not raw prompts or responses:

```bash
python -c "import json; p=json.load(open('docs/data/kendr-catalog-pilot-2026-08-08.json', encoding='utf-8')); print(p['scope']); print(p['pairwise_inference'])"
```

The expected scope is 35 ranked text endpoints plus two N/A non-text entries. The inferential disclosure is zero Holm rejections among 595 comparisons. See the [complete ranking handout](RANKINGS_2026-08-08.md) and [interpretation guide](RESULTS_INTERPRETATION.md).

## 7. Choose the next guide

- Adopting the process in a team: [Adoption guide](ADOPTION_GUIDE.md)
- Planning statistics: [Statistical analysis plan](STATISTICAL_ANALYSIS_PLAN.md)
- Building an execution integration: [Provider adapter guide](PROVIDER_ADAPTER_GUIDE.md)
- Packaging auditable evidence: [Evidence bundle](EVIDENCE_BUNDLE.md)
- Understanding record contracts: [Schema reference](SCHEMA_REFERENCE.md)

Never commit `.env`, provider keys, raw paid-run directories, or unreviewed prompts/responses. The repository intentionally ignores those paths.
