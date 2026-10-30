from pathlib import Path


def write_srt(lines: list[tuple[float, float, str]], out: Path) -> Path:
    def ts(x):
        ms = int(x * 1000)
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    with out.open("w", encoding="utf-8") as f:
        for i, (a, b, text) in enumerate(lines, 1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{text}\n\n")
    return out
