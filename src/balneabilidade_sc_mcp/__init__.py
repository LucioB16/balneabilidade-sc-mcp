"""IMA/SC bathing-water provider.

The package exposes the normalized provider and the local stdio MCP server.
"""

from .provider import ImaProvider

__version__ = "0.1.0"
__all__ = ["ImaProvider", "__version__"]
