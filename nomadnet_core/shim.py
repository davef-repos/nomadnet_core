"""
Backward-compatibility shim: Re-exports nomadnet_core symbols into the
original nomadnet namespace so existing code (and the TUI) continues to work.

Usage (in nomadnet/__init__.py):
    from nomadnet_core.shim import *
"""

# Re-export core classes
from nomadnet_core.core.NomadNetworkApp import NomadNetworkApp, UIBackend
from nomadnet_core.core.Directory import Directory, DirectoryEntry, PNAnnounceHandler
from nomadnet_core.core.Conversation import Conversation, ConversationMessage
from nomadnet_core.core.Node import Node
from nomadnet_core.core.RRC import RRCMessage, RRCHub, RRCManager

import nomadnet_core.core.util as _util
strip_modifiers = _util.strip_modifiers
sanitize_name = _util.sanitize_name
strip_micron = _util.strip_micron
strip_escaped_micron = _util.strip_escaped_micron
unescape_micron = _util.unescape_micron
strip_non_formatting_tags = _util.strip_non_formatting_tags
