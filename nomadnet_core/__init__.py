"""
nomadnet-core: The protocol and data-model layer of NomadNet.

This package contains the reusable core of NomadNet - the networking protocol,
data models, directory management, RRC chat protocol, and markup parsing - all
decoupled from any specific UI framework.

It can be used as a foundation for multiple UIs:
  - The original urwid-based TUI (nomadnet package)
  - A Neovim plugin
  - A Qt/Gtk GUI
  - A web interface
  - A headless daemon
"""

from ._version import __version__

# ── Core application class ────────────────────────────────────────
from .core.NomadNetworkApp import NomadNetworkApp
from .core.NomadNetworkApp import UIBackend

# ── Data models ───────────────────────────────────────────────────
from .core.Conversation import Conversation
from .core.Conversation import ConversationMessage
from .core.Directory import Directory
from .core.Directory import DirectoryEntry
from .core.Directory import PNAnnounceHandler
from .core.Node import Node
from .core.RRC import RRCManager
from .core.RRC import RRCMessage
from .core.RRC import RRCHub

# ── Utilities ────────────────────────────────────────────────────
from .core import util

# ── Protocol layer ────────────────────────────────────────────────
from .protocol import PageFetcher


