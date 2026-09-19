import re as _re
from tray.dashboard.theme import RED, AMBER, MUTED

SEV_COLORS = {
    "ERROR": RED, "CRITICAL": RED,
    "WARNING": AMBER,
    "INFO": "#ffffff",
    "DEBUG": "#94a3b8",
}

TAG_COLORS_MAP = {
    "CORE":   "#4dabf7",  # Bright Blue
    "DAEMON": "#b197fc",  # Purple
    "WEBUI":  "#69db7c",  # Green
    "PLUGIN": "#ffa94d",  # Orange
}

url_pattern = _re.compile(r'(https?://[^\s\'"<>]+)')
tag_pattern  = _re.compile(r'(\[(?:CORE|PLUGIN|WEBUI|DAEMON)[^\]]*\])', _re.IGNORECASE)

def _get_source_tag(txt):
    t = txt.upper()
    if t.startswith("[CORE"):   return "TAG_CORE"
    if t.startswith("[PLUGIN"): return "TAG_PLUGIN"
    if t.startswith("[WEBUI"):  return "TAG_WEBUI"
    if t.startswith("[DAEMON"): return "TAG_DAEMON"
    return None

def parse_log_lines(lines, full_color=True):
    segments_out = []
    for line in lines:
        stripped = line.rstrip()
        col_tag = "MUTED"
        u = stripped.upper()
        for kw in ("ERROR", "CRITICAL", "WARNING", "INFO", "DEBUG"):
            if kw in u:
                col_tag = kw
                break
        if full_color and col_tag in ("INFO", "DEBUG", "MUTED"):
            for seg in url_pattern.split(stripped):
                if url_pattern.match(seg):
                    segments_out.append((seg, ("URL", col_tag)))
                else:
                    for sub in tag_pattern.split(seg):
                        src_tag = _get_source_tag(sub)
                        if src_tag:
                            segments_out.append((sub, (src_tag, col_tag)))
                        else:
                            segments_out.append((sub, col_tag))
        else:
            for p in url_pattern.split(stripped):
                if url_pattern.match(p):
                    segments_out.append((p, ("URL", col_tag)))
                else:
                    segments_out.append((p, col_tag))
        segments_out.append(("\n", col_tag))
    return segments_out
