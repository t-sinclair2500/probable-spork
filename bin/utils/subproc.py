# bin/utils/subproc.py
from collections import deque
import subprocess
import os
from typing import Iterable, Optional, Sequence, Mapping, Union

def _ensure_parent(path: str) -> None:
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)

def run_streamed(
    cmd: Sequence[str],
    cwd: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
    log_path: Optional[str] = None,
    tail_lines: int = 200,
    text: bool = True,
    check: bool = True,
    echo: bool = True,
) -> int:
    """
    Stream a subprocess's output line-by-line to stdout (optional) and tee to a logfile.
    Keep a tail buffer of the last N lines for error messages. Raise on non-zero if check=True.
    Returns process returncode.
    """
    _ensure_parent(log_path) if log_path else None
    tail = deque(maxlen=tail_lines)
    log_fh = open(log_path, "a", encoding="utf-8") if log_path else None
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=dict(os.environ, **env) if env else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=text,
            bufsize=1,  # line-buffered
            universal_newlines=True,
        )
        assert proc.stdout is not None
        for line in iter(proc.stdout.readline, ""):
            tail.append(line.rstrip("\n"))
            if echo:
                print(line, end="")
            if log_fh:
                log_fh.write(line)
        proc.wait()
        rc = proc.returncode
        if check and rc != 0:
            tail_str = "\n".join(tail)
            raise RuntimeError(
                f"Command failed (rc={rc}): {' '.join(cmd)}\n--- tail({len(tail)} lines) ---\n{tail_str}\n"
            )
        return rc
    finally:
        if log_fh:
            log_fh.flush()
            log_fh.close()
