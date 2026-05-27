from pathlib import Path
from shutil import copyfile


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save_file(self, source: Path, relative_path: str) -> Path:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, target)
        return target
