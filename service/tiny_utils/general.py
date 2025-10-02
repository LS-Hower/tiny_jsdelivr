# 2025-10-01  tiny_utils/general.py

import os
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Optional


def report_counted_things(
        n: int,
        singular: str,
        plural: Optional[str] = None
        ) -> str:
    """
    (1, "line")               -> "(1 line)"
    (2, "lines")              -> "(2 lines)"
    (3, "matrix", "matrices") -> "(3 matrices)"
    """
    assert n >= 0
    plural = plural or singular + 's'
    return f"({n} {singular if n <= 1 else plural})"


def reverse_cmp[T](cmp: Callable[[T, T], int]) -> Callable[[T, T], int]:
    def revcmp(x: T, y: T) -> int:
        return -cmp(y, x)
    return revcmp


class PurePosixPathThatMightBeDir(PurePosixPath):
    """
    Same as `PurePosixPath`, but can remember whether it was a directory
    when it was created.
    """
    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._is_dir = path.endswith('/')

    def is_dir(self) -> bool:
        return self._is_dir




def get_folder_size(path: str) -> int:
    """Get the size of a folder in bytes."""
    return sum(get_entry_size(os.path.join(path, f))
               for f in os.listdir(path))


def get_entry_size(path: str) -> int:
    """Get the size of a file or folder in bytes."""
    return os.path.getsize(path) \
               if os.path.isfile(path) \
               else get_folder_size(path)


def size_text(size: int) -> str:
    """Convert a size in bytes to a human-readable string."""
    if size < 1024:
        return "{:d} B".format(size)
    if size < 1024 ** 2:
        return "{:.2f} KiB".format(size / 1024)
    if size < 1024 ** 3:
        return "{:.2f} MiB".format(size / 1024 ** 2)
    return "{:.2f} GiB".format(size / 1024 ** 3)


def yellow_text(text: str) -> str:
    """ANSI coloring for yellow text."""
    return "\033[1;33m{:s}\033[0m".format(text)


