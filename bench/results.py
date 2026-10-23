"""results (split from bench_panel.py)"""

def parse_rows(lines):
    header, rows = None, []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if "test" in cells and "t/s" in cells:
            header = cells
            continue
        if header and len(cells) == len(header) and not set(s) <= set("|-: "):
            try:
                rows.append((cells[header.index("test")], float(cells[-1].split()[0]), cells))
            except (ValueError, IndexError):
                pass
    return header, rows

def best_summary(lines):
    header, rows = parse_rows(lines)
    if not rows:
        return ""
    skip = {"model", "size", "params", "backend", "test", "t/s"}
    cols = [i for i, h in enumerate(header) if h not in skip and len({r[2][i] for r in rows}) > 1]
    best = {}
    for test, ts, cells in rows:
        if test not in best or ts > best[test][0]:
            best[test] = (ts, cells)
    out = ["Best result per test:"]
    for test, (ts, cells) in best.items():
        cfg = ", ".join(f"{header[i]}={cells[i]}" for i in cols) or "-"
        out.append(f"  {test:<8} {ts:>9.2f} t/s   {cfg}")
    return "\n".join(out) + "\n"
