"""LLM Benchmark Protocol reference harness.

The historical ``kendr_bench`` import namespace is retained for compatibility.
"""

from .domain import BenchmarkCase, BenchmarkRecord, Cost, ProviderResult, Usage

__all__ = [
    "BenchmarkCase",
    "BenchmarkRecord",
    "Cost",
    "ProviderResult",
    "Usage",
]

__version__ = "1.0.2"
