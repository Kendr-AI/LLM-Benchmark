from __future__ import annotations

from scripts.freeze_kendr_catalog_panel import freeze_panel


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
