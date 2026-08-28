import json
import csv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from services.exif_service import exif_service, sanitize_keywords
from services.csv_service import generate_shutterstock_csv
from services.ftp_service import FtpUploader
from database.supabase_client import SupabaseManager
from services.phototag_service import (
    ADOBE_CATEGORIES,
    BUYER_PERSONAS,
    SHUTTERSTOCK_CATEGORIES,
    build_custom_context,
    get_target_buyer,
    phototag_service,
)
from services.platform_service import file_is_complete_for_platforms


REQUIRED_KEYS = {
    "title",
    "keywords",
    "adobe_cat",
    "shutter_cat",
    "has_copy_space",
    "camera_angle",
    "target_buyer",
}


def mock_api_payload(index: int) -> dict:
    buyer = get_target_buyer(index)
    return {
        "title": (
            "Commercial stock photograph showing detailed lighting, textures, and composition "
            "for a premium advertising campaign with emotional depth and visual clarity " + ("x" * 20)
        )[:190],
        "keywords": ", ".join([f"keyword phrase {i}" for i in range(1, 51)]),
        "adobe_cat": ADOBE_CATEGORIES[index % len(ADOBE_CATEGORIES)],
        "shutter_cat": SHUTTERSTOCK_CATEGORIES[index % len(SHUTTERSTOCK_CATEGORIES)],
        "has_copy_space": index % 2 == 0,
        "camera_angle": "high angle",
        "target_buyer": buyer,
    }


def test_category_lists_are_complete():
    assert len(ADOBE_CATEGORIES) == 21
    assert len(SHUTTERSTOCK_CATEGORIES) == 28


def test_buyer_rotation():
    buyers = [get_target_buyer(i) for i in range(4)]
    assert buyers == BUYER_PERSONAS
    assert get_target_buyer(4) == BUYER_PERSONAS[0]
    for index, buyer in enumerate(BUYER_PERSONAS):
        prompt = build_custom_context(index)
        assert buyer in prompt
        assert "exactly 50 comma-separated" in prompt.lower()
        assert "185-199" in prompt


def test_keyword_sanitization():
    cleaned = sanitize_keywords("Coffee, coffee,  TEA ,Food, food, extra1")
    assert cleaned == ["coffee", "tea", "food", "extra1"]
    assert len(sanitize_keywords(", ".join(f"Tag {i}" for i in range(80)))) == 50


def test_exif_writes_keywords_as_list_values(tmp_path: Path):
    image_path = tmp_path / "metadata.jpg"
    image_path.write_bytes(b"fake-jpeg")
    keywords = [f"keyword{i}" for i in range(50)]

    def fake_run(command, **kwargs):
        if "-j" in command:
            return SimpleNamespace(stdout=json.dumps([{"Keywords": keywords}]))
        return SimpleNamespace(stdout="")

    with patch("services.exif_service.subprocess.run", side_effect=fake_run) as run:
        assert exif_service.write_metadata(
            image_path,
            "Title",
            "Description",
            keywords,
        )

    assert run.call_count == 3
    clear_command = run.call_args_list[0].args[0]
    command = run.call_args_list[1].args[0]
    assert "-XMP:Subject=" in clear_command
    assert "-IPTC:Keywords=" in clear_command
    assert "-EXIF:XPKeywords=" in clear_command
    assert len([arg for arg in command if arg.startswith("-XMP:Subject+=")]) == 0
    assert len([arg for arg in command if arg.startswith("-IPTC:Keywords+=")]) == 50


def test_phototag_rotation_schema(tmp_path: Path):
    dummy_files = []
    for index in range(4):
        path = tmp_path / f"dummy_{index}.jpg"
        path.write_bytes(b"fake-jpeg")
        dummy_files.append(path)

    def fake_post(*args, **kwargs):
        context = kwargs.get("data", {}).get("customContext", "")
        index = next(i for i, buyer in enumerate(BUYER_PERSONAS) if buyer in context)
        payload = mock_api_payload(index)
        return SimpleNamespace(status_code=200, json=lambda: payload, text=json.dumps(payload))

    with patch("services.phototag_service.requests.post", side_effect=fake_post):
        with patch("services.phototag_service.time.sleep", return_value=None):
            results = []
            for index, path in enumerate(dummy_files):
                result = phototag_service.generate_metadata(path, image_index=index)
                assert result["success"] is True
                assert REQUIRED_KEYS.issubset(result)
                assert result["target_buyer"] == get_target_buyer(index)
                assert isinstance(result["has_copy_space"], bool)
                assert result["adobe_cat"] in ADOBE_CATEGORIES
                shutter_cats = result.get("shutter_cats") or [
                    item.strip()
                    for item in str(result.get("shutter_cat", "")).split(",")
                    if item.strip()
                ]
                assert len(shutter_cats) == 2
                assert all(item in SHUTTERSTOCK_CATEGORIES for item in shutter_cats)
                results.append(result)

    assert [item["target_buyer"] for item in results] == BUYER_PERSONAS


def test_shutterstock_csv(tmp_path: Path):
    output_path = tmp_path / "shutterstock_upload.csv"
    keywords = [f"keyword{i}" for i in range(55)]
    result = generate_shutterstock_csv(
        [{
            "filename": "/photos/example.jpg",
            "description": "Example description",
            "keywords": keywords,
            "categories": ["Nature", "Travel", "Objects"],
        }],
        str(output_path),
    )

    assert result == str(output_path)
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["Filename"] == "example.jpg"
    assert len(rows[0]["Keywords"].split(", ")) == 50
    assert rows[0]["Categories"] == "Nature,Travel"
    assert rows[0]["Editorial"] == "no"
    assert rows[0]["Mature content"] == "no"
    assert rows[0]["illustration"] == "no"


def test_shutterstock_batch_uploads_images_and_keeps_csv(tmp_path: Path):
    first_image = tmp_path / "first.jpg"
    second_image = tmp_path / "second.jpg"
    first_image.write_bytes(b"first")
    second_image.write_bytes(b"second")
    commands = []

    class FakeFtp:
        def connect(self, *args):
            pass

        def login(self, *args):
            pass

        def prot_p(self):
            pass

        def set_pasv(self, *args):
            pass

        def storbinary(self, command, file_obj, blocksize=None):
            commands.append(command)

        def quit(self):
            pass

    items = [
        {"image_path": first_image, "description": "First", "keywords": [f"first{i}" for i in range(48)], "categories": ["Nature"]},
        {"image_path": second_image, "description": "Second", "keywords": [f"second{i}" for i in range(48)], "categories": ["Travel"]},
    ]
    with patch("services.ftp_service.FTP_TLS", return_value=FakeFtp()):
        with patch("services.ftp_service._resolve_password", return_value="password"):
            with patch("services.ftp_service.config.FTP_SHUTTER_USER", "user"):
                ok, detail = FtpUploader().upload_batch_with_csv(items, tmp_path)

    assert ok is True, detail
    assert commands == [
        "STOR first.jpg",
        "STOR second.jpg",
    ]
    assert (tmp_path / "shutterstock_upload.csv").exists()


def test_history_uses_live_supabase_schema():
    class Query:
        def __init__(self):
            self.records = None

        def select(self, value):
            assert value == "*"
            return self

        def order(self, column, desc=False):
            assert column == "updated_at"
            assert desc is True
            return self

        def limit(self, value):
            assert value == 200
            return self

        def upsert(self, records, on_conflict=None):
            self.records = records
            assert on_conflict == "folder_path,filename"
            return self

        def execute(self):
            return SimpleNamespace(data=[{"filename": "photo.jpg", "ftp_done": True}])

    class Client:
        def __init__(self):
            self.query = Query()

        def table(self, name):
            assert name == "uploads"
            return self.query

    manager = SupabaseManager()
    manager._client = Client()
    assert manager.fetch_history() == [{"filename": "photo.jpg", "ftp_done": True}]
    assert manager.log_batch([{
        "folder_path": "/photos",
        "filename": "photo.jpg",
        "adobe_status": True,
        "shutter_status": False,
        "exif_done": True,
    }])
    assert manager.client.query.records == [{
        "folder_path": "/photos",
        "filename": "photo.jpg",
        "phototag_status": "done",
        "adobe_status": "done",
        "shutter_status": "failed",
        "api_done": True,
        "exif_done": True,
        "ftp_done": False,
    }]

    assert manager.log_batch([{
        "folder_path": "/photos",
        "filename": "adobe-only.jpg",
        "adobe_status": True,
        "shutter_status": False,
        "selected_platforms": ["adobe"],
        "exif_done": True,
    }])
    assert manager.client.query.records[0]["adobe_status"] == "done"
    assert manager.client.query.records[0]["shutter_status"] == "skipped"
    assert manager.client.query.records[0]["ftp_done"] is True


def test_platform_specific_completion():
    meta = {
        "exif_done": True,
        "ftp_adobe_done": True,
        "ftp_shutter_done": False,
    }
    assert file_is_complete_for_platforms(meta, {"adobe"}) is True
    assert file_is_complete_for_platforms(meta, {"shutterstock"}) is False
    assert file_is_complete_for_platforms(meta, {"adobe", "shutterstock"}) is False

    meta["ftp_shutter_done"] = True
    assert file_is_complete_for_platforms(meta, {"shutterstock"}) is True
    assert file_is_complete_for_platforms(meta, {"adobe", "shutterstock"}) is True


if __name__ == "__main__":
    test_category_lists_are_complete()
    test_buyer_rotation()
    test_keyword_sanitization()
    test_exif_writes_keywords_as_list_values(Path("/tmp"))
    test_phototag_rotation_schema(Path("/tmp"))
    test_shutterstock_csv(Path("/tmp"))
    test_shutterstock_batch_uploads_images_and_keeps_csv(Path("/tmp"))
    test_history_uses_live_supabase_schema()
    test_platform_specific_completion()
    print("test_pipeline.py passed")
