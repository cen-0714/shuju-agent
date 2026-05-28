from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from shutil import copyfile
from uuid import uuid4


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    absolute_path: Path
    checksum: str
    size_bytes: int


class LocalStorageBackend:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, *, category: str, filename: str, content: bytes) -> StoredFile:
        safe_name = Path(filename).name or "upload.dat"
        relative_path = Path(category) / f"{uuid4().hex}-{safe_name}"
        absolute_path = self.resolve_path(relative_path.as_posix())
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)
        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=absolute_path,
            checksum=sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    def delete_file(self, relative_path: str) -> None:
        path = self.resolve_path(relative_path)
        if path.exists():
            path.unlink()

    def exists(self, relative_path: str) -> bool:
        return self.resolve_path(relative_path).exists()

    def resolve_path(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("path is outside storage root")
        return path


def create_storage_backend(root: str | Path) -> LocalStorageBackend:
    return LocalStorageBackend(root=root)


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.backend = LocalStorageBackend(root)

    def save_file(self, source: Path, relative_path: str) -> Path:
        target = self.backend.resolve_path(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, target)
        return target
