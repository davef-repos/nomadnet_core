# nomadnet-core

The protocol and data-model layer of [NomadNet](https://github.com/markqvist/NomadNet), extracted as a standalone, UI-agnostic library.

## What is this?

NomadNet is an off-grid, resilient mesh communication system with strong encryption, forward secrecy, and extreme privacy, built on [Reticulum](https://github.com/markqvist/Reticulum) and [LXMF](https://github.com/markqvist/LXMF).

This package (`nomadnet-core`) contains the reusable core of NomadNet — the networking protocol, data models, directory management, RRC chat protocol, and markup utilities — all decoupled from any specific UI framework.

This makes it possible to build multiple independent UIs on top of the same foundation:

- The original [urwid-based TUI](https://github.com/markqvist/NomadNet)
- A Neovim plugin
- A Qt/Gtk GUI
- A web interface
- A headless daemon

## Installation

```bash
pip install nomadnet-core
```

Requires Python 3.8+ and the `rns` and `lxmf` packages.

## Usage

```python
from nomadnet_core import NomadNetworkApp, Conversation, Directory, Node
from nomadnet_core.protocol import PageFetcher

# Create the app core (requires RNS/LXMF configuration)
app = NomadNetworkApp(configdir="/path/to/config", daemon=True)

# Work with conversations, directory, nodes etc.
for conv in Conversation.conversation_list(app):
    print(conv)

# Fetch pages from a NomadNet node
fetcher = PageFetcher(app)
fetcher.retrieve_url("lxmf@<destination_hash>/page/index.mu")
```

## Package Structure

```
nomadnet_core/
├── __init__.py          # Package metadata
├── _version.py          # Version string
├── shim.py              # Backward-compat re-exports for the original nomadnet package
├── setup.py             # Package configuration
├── core/
│   ├── __init__.py
│   ├── NomadNetworkApp.py   # Main application class & UIBackend interface
│   ├── Conversation.py      # Conversation and ConversationMessage models
│   ├── Directory.py         # Directory service & DirectoryEntry
│   ├── Node.py              # Node (page/file server) implementation
│   ├── RRC.py               # RRC chat protocol (hubs, messages, manager)
│   └── util.py              # Text sanitization utilities (strip_modifiers, sanitize_name, micron helpers)
├── protocol/
│   ├── __init__.py
│   └── page_fetcher.py      # Network page/file fetcher, cache, URL parsing
└── vendor/
    ├── cbor.py              # CBOR serialization (bundled dependency)
    ├── AsciiChart.py        # ASCII chart rendering (bundled dependency)
    └── quotes.py            # Collection of quotes
```

## Building a UI

To create a custom UI, subclass `UIBackend` and pass it to `NomadNetworkApp`:

```python
from nomadnet_core import NomadNetworkApp
from nomadnet_core.core.NomadNetworkApp import UIBackend

class MyNeovimBackend(UIBackend):
    def on_exit(self, app):
        # Clean up resources
        pass

    def on_message_received(self, message):
        # Handle incoming message
        pass

    def get_glyph(self, name):
        # Return UI-specific glyphs
        pass

    def schedule_redraw(self, callback):
        # Schedule a redraw in the UI thread
        pass
```

## License

GNU General Public License v3.0 — see [LICENSE](./LICENSE).

This package is extracted from [NomadNet](https://github.com/markqvist/NomadNet) by Mark Qvist.
