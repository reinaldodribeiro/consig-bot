"""CheckpointManager — CSV-backed resumable state per bot."""
from __future__ import annotations

import csv
from pathlib import Path

from loguru import logger

from app.utils.dates import now_str
from app.utils.paths import ensure_dir


class CheckpointManager:
    """Tracks processed row_indexes so reruns can skip done work."""

    def __init__(self, checkpoint_dir: Path, bot_key: str) -> None:
        ensure_dir(checkpoint_dir)
        self.file_path = checkpoint_dir / f"{bot_key}_checkpoint.csv"
        self._processed: dict[int, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.file_path.exists():
            with self.file_path.open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(["row_index", "status", "timestamp"])
            return
        with self.file_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    self._processed[int(r["row_index"])] = r.get("status", "")
                except (ValueError, KeyError):
                    continue
        if self._processed:
            logger.debug("Checkpoint: {} linhas já processadas", len(self._processed))

    def is_processed(self, row_index: int) -> bool:
        return row_index in self._processed

    def mark_done(self, row_index: int, status: str) -> None:
        self._processed[row_index] = status
        with self.file_path.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([row_index, status, now_str()])

    def processed_count(self) -> int:
        return len(self._processed)

    def clear(self) -> None:
        self._processed.clear()
        if self.file_path.exists():
            self.file_path.unlink()
        logger.info("Checkpoint limpo: {}", self.file_path)
