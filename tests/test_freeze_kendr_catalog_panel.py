from __future__ import annotations

import pytest

from scripts.freeze_kendr_catalog_panel import (
    CatalogIdentityError,
    catalog_audit,
    freeze_panel,
)


def test_freeze_panel_selects_available_text_entries() -> None:
    catalog = [
        {
            "id": "text-model",
            "display_name": "Text Model",
            "available": True,
            "capabilities": ["text", "tools"],
        },
        {
            "id": "image-model",
            "display_name": "Image Model",
            "available": True,
            "capabilities": ["image_generation"],
        },
        {
            "id": "offline-model",
            "available": False,
            "capabilities": ["text"],
        },
    ]

    panel = freeze_panel(catalog)

    assert [item["model"] for item in panel] == ["text-model"]
    assert panel[0]["provider"] == "kendr"


def test_freeze_panel_can_include_specialized_entries() -> None:
    catalog = [
        {
            "id": "image-model",
            "available": True,
            "capabilities": ["image_generation"],
        }
    ]

    assert freeze_panel(catalog, include_non_text=True)[0]["model"] == "image-model"


def test_freeze_panel_excludes_user_owned_aliases_by_default() -> None:
    catalog = [
        {
            "id": "shared-model",
            "display_name": "Shared Model",
            "owned_by": "kendr",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "personal-router",
            "display_name": "My Router",
            "owned_by": "kendr-user",
            "custom_routing_profile": True,
            "available": True,
            "capabilities": ["text"],
        },
    ]

    assert [row["model"] for row in freeze_panel(catalog)] == ["shared-model"]
    assert [
        row["model"]
        for row in freeze_panel(catalog, include_user_owned=True)
    ] == ["shared-model", "personal-router"]
    audit = catalog_audit(catalog)
    assert audit["excluded_entries"][0]["reason"] == (
        "user-owned alias excluded by default"
    )


def test_freeze_panel_rejects_duplicate_normalized_labels() -> None:
    catalog = [
        {
            "id": "provider-a-model",
            "display_name": "Model X 1.0",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "provider-b-model",
            "display_name": "model-x 1.0",
            "available": True,
            "capabilities": ["text"],
        },
    ]

    with pytest.raises(CatalogIdentityError, match="identity review"):
        freeze_panel(catalog)

    audit = catalog_audit(catalog)
    assert audit["identity_status"] == "fail"
    assert audit["duplicate_display_label_groups"] == [
        {
            "normalized_label": "modelx10",
            "display_name": "Model X 1.0",
            "catalog_ids": ["provider-a-model", "provider-b-model"],
            "resolution": (
                "identity unresolved; do not merge or describe as distinct "
                "physical models without route evidence"
            ),
        }
    ]


def test_freeze_panel_can_annotate_duplicate_labels_without_merging() -> None:
    catalog = [
        {
            "id": "provider-a-model",
            "display_name": "Model X",
            "available": True,
            "capabilities": ["text"],
        },
        {
            "id": "provider-b-model",
            "display_name": "Model X",
            "available": True,
            "capabilities": ["text"],
        },
    ]

    panel = freeze_panel(catalog, duplicate_label_policy="annotate")

    assert [row["model"] for row in panel] == [
        "provider-a-model",
        "provider-b-model",
    ]
    assert all("identity unresolved" in row["label"] for row in panel)
    assert all(row["model"] in row["label"] for row in panel)
