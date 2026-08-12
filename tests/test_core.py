#!/usr/bin/env python3
"""
Verification tests for the standalone nomadnet-core library.

This package contains the protocol and data-model layer of NomadNet,
decoupled from any UI framework, suitable for use in a Neovim plugin
or other custom UIs.

Run with:
    pip install -e . && python3 tests/test_core.py
"""

import sys
import os
import tempfile
import traceback

PASS = 0
FAIL = 0

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✓ {name}")
    except Exception as e:
        FAIL += 1
        print(f"  ✗ {name}: {e}")
        traceback.print_exc()

_app_cache = None

def setup_app():
    """Create a minimal NomadNetworkApp for testing.
    Uses singleton pattern because RNS.Reticulum can only be initialized once.
    """
    global _app_cache
    if _app_cache is not None:
        return _app_cache

    tmpdir = tempfile.mkdtemp()
    os.makedirs(tmpdir + '/storage', exist_ok=True)
    with open(tmpdir + '/config', 'w') as f:
        f.write('[client]\nenable_client = True\nuser_interface = none\n')
    rnsdir = tmpdir + '/.rns'
    os.makedirs(rnsdir + '/storage', exist_ok=True)

    import RNS
    RNS.loglevel = 0  # Silent
    RNS.logdest = RNS.LOG_STDOUT

    from nomadnet_core import NomadNetworkApp
    NomadNetworkApp.configdir = tmpdir

    app = NomadNetworkApp(
        configdir=tmpdir,
        rnsconfigdir=rnsdir,
        daemon=True
    )
    _app_cache = (app, tmpdir)
    return _app_cache


print("=" * 60)
print("nomadnet-core Standalone Library Tests")
print("=" * 60)

# ─── Test 1: Package imports ──────────────────────────────────────
print("\n1. Package imports")

def test_core_package_import():
    import nomadnet_core
    assert hasattr(nomadnet_core, '__version__')
    assert hasattr(nomadnet_core, 'NomadNetworkApp')
    assert hasattr(nomadnet_core, 'Conversation')
    assert hasattr(nomadnet_core, 'ConversationMessage')
    assert hasattr(nomadnet_core, 'Directory')
    assert hasattr(nomadnet_core, 'DirectoryEntry')
    assert hasattr(nomadnet_core, 'Node')
    assert hasattr(nomadnet_core, 'RRCManager')
    assert hasattr(nomadnet_core, 'RRCMessage')
    assert hasattr(nomadnet_core, 'RRCHub')

test("nomadnet_core package top-level exports", test_core_package_import)

def test_util_import():
    from nomadnet_core import util
    assert callable(util.strip_modifiers)
    assert callable(util.sanitize_name)
    assert callable(util.strip_micron)
    assert callable(util.strip_escaped_micron)
    assert callable(util.unescape_micron)
    assert callable(util.strip_non_formatting_tags)

test("util module functions", test_util_import)

def test_protocol_import():
    from nomadnet_core.protocol import PageFetcher

test("protocol.PageFetcher import", test_protocol_import)

def test_ui_backend_import():
    from nomadnet_core.core.NomadNetworkApp import UIBackend

test("UIBackend importable", test_ui_backend_import)

# ─── Test 2: Test UIBackend abstraction ───────────────────────────
print("\n2. UIBackend abstraction")

def test_ui_backend_subclass():
    """UIBackend can be subclassed to create custom UIs."""
    from nomadnet_core.core.NomadNetworkApp import UIBackend

    class MyBackend(UIBackend):
        def __init__(self):
            self.exit_called = False
            self.msg_received = None
            self.glyph = None
            self.redraw_called = False

        def on_exit(self, app):
            self.exit_called = True

        def on_message_received(self, app):
            self.msg_received = app

        def get_glyph(self, name):
            if name == "sent":
                return "→"
            return None

        def schedule_redraw(self, app, delay=0.0):
            self.redraw_called = True

    backend = MyBackend()
    assert isinstance(backend, UIBackend)
    backend.on_exit("app")
    assert backend.exit_called
    backend.on_message_received("msg")
    assert backend.msg_received == "msg"
    assert backend.get_glyph("sent") == "→"
    assert backend.get_glyph("unknown") is None
    backend.schedule_redraw("app")
    assert backend.redraw_called

test("UIBackend subclassing works", test_ui_backend_subclass)

def test_ui_backend_defaults():
    """UIBackend default methods are no-ops, not abstract."""
    from nomadnet_core.core.NomadNetworkApp import UIBackend
    backend = UIBackend()
    backend.on_exit(None)          # Should not raise
    backend.on_message_received(None)  # Should not raise
    assert backend.get_glyph("sent") is None
    backend.schedule_redraw(None)  # Should not raise

test("UIBackend no-op defaults", test_ui_backend_defaults)

# ─── Test 3: Core app initialization ──────────────────────────────
print("\n3. Core app initialization")

def test_app_create():
    app, tmpdir = setup_app()
    assert app is not None
    assert hasattr(app, 'version')
    assert hasattr(app, 'identity')
    assert hasattr(app, 'message_router')
    assert hasattr(app, 'directory')
    assert hasattr(app, 'rrc')

test("NomadNetworkApp creates successfully", test_app_create)

def test_app_ui_backend():
    app, tmpdir = setup_app()
    assert app._ui_backend is not None
    assert hasattr(app._ui_backend, 'on_exit')
    assert hasattr(app._ui_backend, 'on_message_received')

test("UI backend abstraction works", test_app_ui_backend)

def test_app_directory():
    app, tmpdir = setup_app()
    assert app.directory is not None
    assert hasattr(app.directory, 'find')
    assert hasattr(app.directory, 'simplest_display_str')

test("Directory service initialized", test_app_directory)

def test_app_rrc():
    app, tmpdir = setup_app()
    assert app.rrc is not None

test("RRC manager initialized", test_app_rrc)

def test_app_daemon_mode():
    """Verify daemon=True doesn't start UI."""
    app, tmpdir = setup_app()
    assert app.uimode == "none"

test("Daemon mode sets correct uimode", test_app_daemon_mode)

# ─── Test 4: Core class imports ───────────────────────────────────
print("\n4. Core class imports")

def test_core_version():
    from nomadnet_core import __version__
    assert isinstance(__version__, str)
    assert len(__version__) > 0

test("nomadnet_core version string", test_core_version)

def test_core_class_import():
    from nomadnet_core.core.NomadNetworkApp import NomadNetworkApp, UIBackend
    assert issubclass(NomadNetworkApp, object)
    assert issubclass(UIBackend, object)

test("Core classes import directly", test_core_class_import)

def test_directory_import():
    from nomadnet_core.core.Directory import Directory, DirectoryEntry
    assert hasattr(Directory, 'find')
    assert hasattr(DirectoryEntry, '__init__')
    assert DirectoryEntry.TRUSTED == 0xFF
    assert DirectoryEntry.UNKNOWN == 0x02

test("Directory from nomadnet_core", test_directory_import)

def test_conversation_import():
    from nomadnet_core.core.Conversation import Conversation, ConversationMessage
    assert hasattr(Conversation, 'unread_conversations')
    assert hasattr(Conversation, 'conversation_list')
    assert hasattr(ConversationMessage, '__init__')
    assert hasattr(Conversation, 'ingest')

test("Conversation from nomadnet_core", test_conversation_import)

def test_rrc_import():
    from nomadnet_core.core.RRC import RRCMessage, RRCHub, RRCManager
    assert hasattr(RRCManager, 'load')
    assert hasattr(RRCManager, 'save')

test("RRC from nomadnet_core", test_rrc_import)

def test_node_import():
    from nomadnet_core.core.Node import Node
    assert hasattr(Node, '__init__')
    assert hasattr(Node, 'announce')

test("Node from nomadnet_core", test_node_import)

# ─── Test 5: Protocol layer ──────────────────────────────────────
print("\n5. Protocol layer")

def test_page_fetcher_import():
    from nomadnet_core.protocol import PageFetcher

test("PageFetcher protocol import", test_page_fetcher_import)

def test_parse_url():
    from nomadnet_core.protocol import PageFetcher
    fetcher = PageFetcher.__new__(PageFetcher)

    # Test lxmf@ URL
    result = PageFetcher.parse_url(fetcher, "lxmf@aabbccddee001122/page/index.mu")
    assert result is not None
    dest_hash, path, req_data = result
    assert dest_hash == "aabbccddee001122"
    assert path == "/page/index.mu"
    assert req_data is None

    # Test lxmf@ URL with request data
    result = PageFetcher.parse_url(fetcher, "lxmf@aabbccddee001122/page/index.mu#anchor1")
    assert result is not None
    assert result[2] == "anchor1"

    # Test plain hash URL
    result = PageFetcher.parse_url(fetcher, "aabbccddee001122")
    assert result is not None
    assert result[0] == "aabbccddee001122"

    # Test invalid URL
    result = PageFetcher.parse_url(fetcher, "not-a-valid-url")
    assert result is None

test("PageFetcher.parse_url works", test_parse_url)

# ─── Test 6: Text utilities ──────────────────────────────────────
print("\n6. Text utilities")

def test_strip_modifiers():
    from nomadnet_core.core.util import strip_modifiers

    # None input returns None
    assert strip_modifiers(None) is None

    # Normal text passes through
    assert strip_modifiers("Hello World") == "Hello World"

    # Strip zero-width characters
    result = strip_modifiers("Hello\u200BWorld")
    assert "\u200B" not in result

test("strip_modifiers works", test_strip_modifiers)

def test_sanitize_name():
    from nomadnet_core.core.util import sanitize_name

    # None returns None
    assert sanitize_name(None) is None

    # Simple name passes through
    result = sanitize_name("Alice")
    assert result == "Alice"

    # Emoji stripped
    result = sanitize_name("Alice 😀")
    assert result == "Alice"

    # Normalize NFKC (e.g. full-width chars)
    result = sanitize_name("\uff21")  # Full-width 'A'
    assert result == "A"

test("sanitize_name works", test_sanitize_name)

def test_strip_micron():
    from nomadnet_core.core.util import strip_micron

    # Strip color codes
    result = strip_micron("`F123colored text")
    assert "`F123" not in result
    assert "colored text" in result

    # Strip inline formatting
    result = strip_micron("`*bold`* text")
    assert result == "bold text"

test("strip_micron works", test_strip_micron)

# ─── Test 7: Directory model ─────────────────────────────────────
print("\n7. Directory model")

def test_directory_entry():
    from nomadnet_core.core.Directory import DirectoryEntry

    # Reticulum truncated hash is 16 bytes (32 hex chars) for truncated,
    # but DirectoryEntry expects TRUNCATED_HASHLENGTH//8 bytes.
    # RNS.Identity.TRUNCATED_HASHLENGTH is 128 bits = 16 bytes
    import RNS
    hash_len = RNS.Identity.TRUNCATED_HASHLENGTH // 8
    source_hash = bytes(range(hash_len))  # hash_len unique bytes
    entry = DirectoryEntry(source_hash, display_name="Test Node", trust_level=DirectoryEntry.TRUSTED)

    assert entry.source_hash == source_hash
    assert entry.display_name == "Test Node"
    assert entry.trust_level == DirectoryEntry.TRUSTED
    assert entry.hosts_node == False
    assert entry.preferred_delivery == DirectoryEntry.DIRECT
    assert entry.notes == ""

test("DirectoryEntry creation", test_directory_entry)

# ─── Summary ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"Results: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
