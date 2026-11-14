"""IMA/SC bathing-water provider.

Phase 2 implements the normalized provider only; the MCP server is Phase 3.
"""

from .provider import ImaProvider

__version__ = "0.1.0"
__all__ = ["ImaProvider", "__version__"]
