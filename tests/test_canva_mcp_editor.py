from grume.canva_mcp_client import CanvaMcpEditor
from grume.models import PageCopy, PostPackage


def test_build_operations_targets_background_and_captions():
    transaction = {
        "pages": [
            {"page_id": "PAGE1", "page_number": 1},
            {"page_id": "PAGE2", "page_number": 2},
        ],
        "fills": [
            {"type": "image", "page_index": 1, "editable": True, "element_id": "PAGE1"},
            {"type": "image", "page_index": 2, "editable": True, "element_id": "PAGE2"},
        ],
        "richtexts": [
            {
                "page_index": 1,
                "element_id": "STORE",
                "regions": [{"type": "character", "text": "📍蟹かに城"}],
                "containerElement": {"position": {"top": 190}},
            },
            {
                "page_index": 1,
                "element_id": "SUB",
                "regions": [{"type": "character", "text": "都会の避暑地\n夏を涼む"}],
                "containerElement": {"position": {"top": 960}},
            },
            {
                "page_index": 1,
                "element_id": "HOOK",
                "regions": [{"type": "character", "text": "\\夏とゆえば鱧！！/"}],
                "containerElement": {"position": {"top": 100}},
            },
            {
                "page_index": 1,
                "element_id": "STATION",
                "regions": [{"type": "character", "text": "日本橋"}],
                "containerElement": {"position": {"top": 150}},
            },
            {
                "page_index": 1,
                "element_id": "AREA",
                "regions": [{"type": "character", "text": "大阪"}],
                "containerElement": {"position": {"top": 90}},
            },
            {
                "page_index": 2,
                "element_id": "CAPTION2",
                "regions": [{"type": "character", "text": "本日は蟹かに城さんに！"}],
            },
        ],
    }
    post = PostPackage(
        design_title="焼肉しょうちゃん 天満｜粋コース",
        store_name="焼肉しょうちゃん 天満",
        area="大阪",
        nearest_station="天満",
        cover_subcopy="厚切りタンから特上ハラミまで",
        cover_hook="肉好き必見！",
        pages=[
            PageCopy(page_index=1, filename="01.jpg", dish_name=None, text="cover"),
            PageCopy(page_index=2, filename="02.jpg", dish_name=None, text="店内からスタート✨"),
        ],
    )
    profile = {
        "page1": {
            "store_prefix": "📍",
            "hook_contains": "\\",
            "station_source_text": "日本橋",
            "area_source_text": "大阪",
        }
    }
    operations = CanvaMcpEditor.build_operations(
        transaction,
        post,
        {"01.jpg": "ASSET1", "02.jpg": "ASSET2"},
        profile,
    )

    fills = [o for o in operations if o["type"] == "update_fill"]
    assert fills == [
        {
            "type": "update_fill",
            "element_id": "PAGE1",
            "asset_type": "image",
            "asset_id": "ASSET1",
            "alt_text": "焼肉しょうちゃん 天満",
        },
        {
            "type": "update_fill",
            "element_id": "PAGE2",
            "asset_type": "image",
            "asset_id": "ASSET2",
            "alt_text": "焼肉しょうちゃん 天満",
        },
    ]

    replacements = {
        o["element_id"]: o["text"]
        for o in operations
        if o["type"] == "replace_text"
    }
    assert replacements["STORE"] == "📍焼肉しょうちゃん 天満"
    assert replacements["STATION"] == "天満"
    assert replacements["AREA"] == "大阪"
    assert replacements["CAPTION2"] == "店内からスタート✨"
