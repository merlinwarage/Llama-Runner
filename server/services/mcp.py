"""MCP enablement and --mcp-servers-config resolution (split from server_panel.py)"""
import os

from server.args import unquote
from server.constants import FALSE, TRUE


class McpMixin:
    """MCP enablement and --mcp-servers-config resolution."""
    def mcp_enabled(self, merged):
        # per-model 'mcp = on/off' (or inherited from [*]) wins over the global Settings checkbox
        v = unquote(merged.get("mcp", "")).lower()
        if v and v in TRUE:
            return True
        if v and v in FALSE:
            return False
        return self.s.get("use_mcp") == "1"

    def mcp_args(self, exe, merged):
        # returns (args, error); path is tried against the app folder, then the llama-server folder
        if not self.mcp_enabled(merged):
            return [], None
        raw = unquote(self.s.get("mcp_config", ""))
        if not raw:
            return [], "MCP is enabled but no config path is set (Settings tab)."
        cands = [raw] if os.path.isabs(raw) else [os.path.normpath(os.path.join(self.app_dir, raw)),
                                                  os.path.normpath(os.path.join(os.path.dirname(exe), raw))]
        for c in cands:
            if os.path.isfile(c):
                return ["--mcp-servers-config", c], None
        return ["--mcp-servers-config", cands[0]], "MCP config not found: " + " | ".join(cands)
