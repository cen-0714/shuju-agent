from pathlib import Path

from app.core.storage import LocalStorageBackend


def test_local_storage_saves_and_deletes_file(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root=tmp_path)

    saved = storage.save_upload(
        category="raw",
        filename="business.csv",
        content=b"Date,Sales\n2026-05-27,100\n",
    )

    assert saved.relative_path.startswith("raw/")
    assert saved.absolute_path.exists()
    assert saved.checksum
    assert saved.size_bytes > 0

    storage.delete_file(saved.relative_path)

    assert not saved.absolute_path.exists()


def test_local_storage_resolve_rejects_escape(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root=tmp_path)

    try:
        storage.resolve_path("../outside.csv")
    except ValueError as exc:
        assert "outside storage root" in str(exc)
    else:
        raise AssertionError("Expected path escape to fail")
