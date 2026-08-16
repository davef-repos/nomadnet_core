"""
Page fetching and caching protocol for NomadNet nodes.

This is the protocol-level layer extracted from the Browser, decoupled from
any UI rendering. It handles:
- Requesting pages from NomadNet nodes over Reticulum
- Link following and path resolution
- Page caching
- Partial content delivery
- File downloads from nodes

Usage:
    fetcher = PageFetcher(app)
    fetcher.retrieve_url("lxmf@<hash>/page/index.mu")
    # ... wait for callbacks ...
    content = fetcher.page_data  # Raw micron markup
"""

import os
import time
import threading
import RNS
import LXMF


class PageFetcher:
    """Protocol-level page fetcher for NomadNet nodes.

    Fetches pages and files from NomadNet nodes over Reticulum/LXMF links.
    UI-agnostic: produces raw content (micron markup, binary data) and
    calls registered callbacks.
    """

    DEFAULT_TIMEOUT    = 10
    DEFAULT_CACHE_TIME = 12 * 60 * 60
    DEFAULT_PATH       = "/page/index.mu"

    NO_PATH            = 0x00
    PATH_REQUESTED     = 0x01
    ESTABLISHING_LINK  = 0x02
    LINK_TIMEOUT       = 0x03
    LINK_ESTABLISHED   = 0x04
    REQUEST_SENT       = 0x05
    RESPONSE_RECEIVED  = 0x06
    REQUEST_FAILED     = 0x07
    REQUEST_TIMEOUT    = 0x08
    CACHED             = 0x09
    CONNECTION_CLOSED  = 0x0a

    HASH_LENGTH = 8       # Reticulum truncated hash length (bytes, 16 hex chars)
    HASH_BITS   = 64

    # Page received with data
    PAGE_OK             = 0x00
    # Generic page error
    PAGE_ERROR          = 0x01
    # Node not found / no path
    PAGE_NO_PATH        = 0x02
    # Link establishment failed
    PAGE_NO_LINK        = 0x03
    # Page request timed out
    PAGE_TIMEOUT        = 0x04
    # Page was loaded from local cache
    PAGE_CACHED         = 0x06

    CONTENT_PAGE           = 0x00
    CONTENT_FILE           = 0x01
    CONTENT_PAGE_PARTIAL   = 0x02
    CONTENT_PAGE_MULTIPART = 0x03

    def __init__(self, app):
        self.app = app

        # Current fetch state
        self.last_requested_url = None
        self.current_url        = None
        self.current_destination_hash = None
        self.current_path       = None
        self.status             = PageFetcher.NO_PATH
        self.content_type       = PageFetcher.CONTENT_PAGE

        # Response data
        self.page_data          = None
        self.page_meta          = {}
        self.page_error         = None
        self.response_data      = None

        # History
        self.history            = []
        self.history_position   = -1

        # Callbacks
        self._on_page_ready     = None     # callback(content, meta)
        self._on_page_error     = None     # callback(error_code, error_msg)
        self._on_progress       = None     # callback(percent, bytes_done, bytes_total)

        # Request internals
        self._link              = None
        self._request_data      = None
        self._partials          = {}
        self._timeout_timer     = None
        self._cache_dir         = app.cachepath if hasattr(app, "cachepath") else None

    # --- Callback registration ---

    def on_page_ready(self, callback):
        """Register callback(content, meta) called when a page is fetched."""
        self._on_page_ready = callback

    def on_page_error(self, callback):
        """Register callback(error_code, error_msg) on failure."""
        self._on_page_error = callback

    def on_progress(self, callback):
        """Register callback(percent, bytes_done, bytes_total) for progress."""
        self._on_progress = callback

    # --- URL handling ---

    def parse_url(self, url):
        """Parse a nomadnet URL into (destination_hash, path, request_data).

        Returns None if the URL is invalid.
        """
        if url is None:
            return None

        url = url.strip()

        # lxmf@<hash> or lxmf@<hash>/path
        if url.startswith("lxmf@") or url.startswith("LXMF@"):
            url = url[5:]  # strip "lxmf@" prefix
            if url.startswith("//"):
                url = url[2:]

            hash_end = url.find("/")
            if hash_end == -1:
                destination_hash = url
                path = ""
            else:
                destination_hash = url[:hash_end]
                path = url[hash_end:]

            # Extract request data (hash after #)
            request_data = None
            if "#" in path:
                parts = path.split("#", 1)
                path = parts[0]
                request_data = parts[1]

            return (destination_hash, path, request_data)

        # Plain hash or hash/path
        elif len(url) >= 16 and all(c in "0123456789abcdefABCDEF" for c in url[:16]):
            hash_end = url.find("/")
            if hash_end == -1:
                destination_hash = url
                path = ""
            else:
                destination_hash = url[:hash_end]
                path = url[hash_end:]

            request_data = None
            if "#" in path:
                parts = path.split("#", 1)
                path = parts[0]
                request_data = parts[1]

            return (destination_hash, path, request_data)

        return None

    def retrieve_url(self, url):
        """Request a page from a URL.

        The page is fetched over the network or loaded from cache.
        Results are delivered via registered callbacks.
        """
        self.last_requested_url = url
        parsed = self.parse_url(url)

        if parsed is None:
            self._notify_error(PageFetcher.PAGE_ERROR, "Invalid URL: " + str(url))
            return

        dest_hash, path, request_data = parsed
        self.current_destination_hash = dest_hash
        self.current_path = path
        self._request_data = request_data
        self.content_type = PageFetcher.CONTENT_PAGE

        # Check cache first
        if self._load_from_cache(dest_hash, path):
            return

        # Request from network
        self._request_from_node(dest_hash, path, request_data)

    def download_file(self, url):
        """Download a file from a URL."""
        self.last_requested_url = url
        parsed = self.parse_url(url)

        if parsed is None:
            self._notify_error(PageFetcher.PAGE_ERROR, "Invalid URL: " + str(url))
            return

        dest_hash, path, request_data = parsed
        self.current_destination_hash = dest_hash
        self.current_path = path
        self.content_type = PageFetcher.CONTENT_FILE

        self._request_from_node(dest_hash, path, request_data)

    def back(self):
        """Navigate back in history."""
        if self.history_position > 0:
            self.history_position -= 1
            url = self.history[self.history_position]
            self.retrieve_url(url)

    def forward(self):
        """Navigate forward in history."""
        if self.history_position < len(self.history) - 1:
            self.history_position += 1
            url = self.history[self.history_position]
            self.retrieve_url(url)

    # --- Cache ---

    def _cache_key(self, dest_hash, path):
        return dest_hash + path.replace("/", "_")

    def _load_from_cache(self, dest_hash, path):
        if not self._cache_dir:
            return False

        import RNS.vendor.umsgpack as msgpack

        cache_key = self._cache_key(dest_hash, path)
        cache_path = os.path.join(self._cache_dir, cache_key)

        if not os.path.isfile(cache_path):
            return False

        try:
            with open(cache_path, "rb") as f:
                cached = msgpack.unpackb(f.read())

            cache_time = cached.get("time", 0)
            if time.time() - cache_time > PageFetcher.DEFAULT_CACHE_TIME:
                os.unlink(cache_path)
                return False

            self.page_data = cached.get("data")
            self.page_meta = cached.get("meta", {})
            self.status = PageFetcher.CACHED
            self.current_url = self.last_requested_url

            self._write_history(self.last_requested_url)
            self._notify_ready()
            return True

        except Exception:
            return False

    def _save_to_cache(self, dest_hash, path, data, meta=None):
        if not self._cache_dir:
            return

        import RNS.vendor.umsgpack as msgpack

        try:
            cache_key = self._cache_key(dest_hash, path)
            cache_path = os.path.join(self._cache_dir, cache_key)

            cached = {
                "time": time.time(),
                "data": data,
                "meta": meta or {},
            }

            with open(cache_path, "wb") as f:
                f.write(msgpack.packb(cached))

        except Exception as e:
            RNS.log("Could not cache page: " + str(e), RNS.LOG_DEBUG)

    def clean_cache(self):
        """Remove expired cache entries."""
        if not self._cache_dir or not os.path.isdir(self._cache_dir):
            return

        for fname in os.listdir(self._cache_dir):
            fpath = os.path.join(self._cache_dir, fname)
            if os.path.isfile(fpath):
                try:
                    mtime = os.path.getmtime(fpath)
                    if time.time() - mtime > PageFetcher.DEFAULT_CACHE_TIME:
                        os.unlink(fpath)
                except Exception:
                    pass

    # --- Network request ---

    def _request_from_node(self, dest_hash, path, request_data=None):
        """Initiate a network request to a node.

        If no path is known yet, requests path resolution and resolves
        it asynchronously via a background thread using RNS.Transport.await_path.
        """
        try:
            dest_bytes = bytes.fromhex(dest_hash)
            RNS.log(f"[PageFetcher] Requesting from node {RNS.hexrep(dest_bytes, delimit=False)}, path={path}", RNS.LOG_VERBOSE)
        except (ValueError, AttributeError) as e:
            self._notify_error(PageFetcher.PAGE_ERROR, "Invalid destination hash: " + str(e))
            return

        if not RNS.Transport.has_path(dest_bytes):
            self.status = PageFetcher.PATH_REQUESTED
            RNS.Transport.request_path(dest_bytes)

            # Start a background thread that waits for path resolution
            # using RNS.Transport.await_path (blocks with its own timeout).
            # This keeps the caller unblocked while path discovery happens.
            def wait_for_path(dest_bytes, path, request_data):
                try:
                    timeout = self.DEFAULT_TIMEOUT
                    path_found = RNS.Transport.await_path(dest_bytes, timeout=timeout)
                    if path_found:
                        if self.status in (PageFetcher.CONNECTION_CLOSED, PageFetcher.NO_PATH):
                            return
                        self.status = PageFetcher.ESTABLISHING_LINK
                        self._establish_link(dest_bytes, path, request_data)
                    else:
                        self._notify_error(PageFetcher.PAGE_NO_PATH,
                                           "No path to " + RNS.hexrep(dest_bytes, delimit=False))
                except Exception as e:
                    self._notify_error(PageFetcher.PAGE_ERROR,
                                       "Path resolution error: " + str(e))

            t = threading.Thread(
                target=wait_for_path,
                args=(dest_bytes, path, request_data),
                daemon=True,
            )
            t.start()
            return

        self.status = PageFetcher.ESTABLISHING_LINK
        self._establish_link(dest_bytes, path, request_data)

    def _establish_link(self, dest_bytes, path, request_data=None):
        """Establish a Reticulum link to the node and request the page.

        Uses RNS.Link + link.request() to fetch pages via the node's
        registered request handlers ("nomadnetwork", "node" aspect).
        """
        try:
            # Recall the identity from the destination hash
            identity = RNS.Identity.recall(dest_bytes)
            if identity is None:
                self._notify_error(PageFetcher.PAGE_NO_PATH,
                                   "Unknown identity for " + RNS.hexrep(dest_bytes, delimit=False))
                return

            # Create an outbound destination matching the node's aspect
            node_dest = RNS.Destination(
                identity,
                RNS.Destination.OUT,
                RNS.Destination.SINGLE,
                "nomadnetwork",
                "node",
            )

            # Establish a link to the node
            self._link = RNS.Link(node_dest)

            request_path = path if path else PageFetcher.DEFAULT_PATH

            self._request_data = request_data
            self._partials = {}

            # Register link callbacks
            self._link.set_link_established_callback(self._on_link_established)
            self._link.set_link_closed_callback(self._on_link_closed)

            # Set a generous timeout for the overall operation (link establishment
            # + request). The link.request() call has its own shorter timeout
            # that covers just the request/response exchange.
            overall_timeout = PageFetcher.DEFAULT_TIMEOUT * 2
            self._timeout_timer = threading.Timer(
                overall_timeout,
                self._on_timeout,
            )
            self._timeout_timer.daemon = True
            self._timeout_timer.start()

            # Wait for link to be established before sending request
            # The link established callback will trigger the actual request

        except Exception as e:
            import traceback
            traceback.print_exc()
            self._notify_error(PageFetcher.PAGE_ERROR, "Link error: " + str(e))

    def _on_link_established(self, link):
        """Called when the RNS link is established. Sends the page request."""
        self.status = PageFetcher.LINK_ESTABLISHED

        request_path = self.current_path if self.current_path else PageFetcher.DEFAULT_PATH

        # Send the request via RNS.Link.request()
        # The node's request handler will match the path and return
        # the page content.
        link.request(
            request_path,
            data=None,
            response_callback=self._on_request_response,
            failed_callback=self._on_request_failed,
            progress_callback=self._on_request_progress,
            timeout=PageFetcher.DEFAULT_TIMEOUT,
        )
        self.status = PageFetcher.REQUEST_SENT

    def _on_link_closed(self, link):
        if self.status == PageFetcher.REQUEST_SENT or self.status == PageFetcher.ESTABLISHING_LINK:
            self._notify_error(PageFetcher.PAGE_TIMEOUT, "Connection closed before response")

    def _on_request_response(self, request_receipt):
        """Called when a page response is received from the node.

        The request_receipt is a RNS.RequestReceipt instance.
        Call get_response() to get the response data as bytes.
        """
        response = request_receipt.get_response()
        self.response_received(response)

    def _on_request_failed(self, request_receipt):
        """Called when a page request fails."""
        reason = "Request failed"
        if hasattr(request_receipt, 'status'):
            status_map = {
                RNS.RequestReceipt.FAILED: "Request failed",
                RNS.RequestReceipt.SENT: "Request not delivered",
            }
            reason = status_map.get(request_receipt.status, f"Request status {request_receipt.status}")
        self._notify_error(PageFetcher.REQUEST_FAILED, reason)

    def _on_request_progress(self, request_receipt):
        """Called periodically during response download."""
        if self._on_progress:
            self._on_progress(request_receipt.progress, 0, 0)

    def _on_timeout(self):
        if self.status != PageFetcher.RESPONSE_RECEIVED and self.status != PageFetcher.CACHED:
            self._notify_error(PageFetcher.PAGE_TIMEOUT, "Request timed out")

    # --- Response handling (to be called by external link receiver) ---

    def response_received(self, data):
        """Called when response data arrives from the node."""
        if self._timeout_timer:
            self._timeout_timer.cancel()

        self.status = PageFetcher.RESPONSE_RECEIVED
        self.response_data = data

        if self.content_type == PageFetcher.CONTENT_FILE:
            self.page_data = data
            self._notify_ready()
            return

        # Parse page content
        try:
            content = data.decode("utf-8")
            self.page_data = content
            self.page_meta["content_type"] = "micron"

            # Cache the page
            if self.current_destination_hash and self.current_path is not None:
                self._save_to_cache(self.current_destination_hash,
                                    self.current_path or PageFetcher.DEFAULT_PATH,
                                    content)

            self._write_history(self.last_requested_url)
            self._notify_ready()

        except UnicodeDecodeError:
            self.page_data = data
            self.page_meta["content_type"] = "binary"
            self._notify_ready()

    def response_progressed(self, progress, total):
        """Called during partial content delivery."""
        if self._on_progress:
            percent = (progress / total) * 100 if total > 0 else 0
            self._on_progress(percent, progress, total)

    def request_failed(self, reason):
        """Called when the request fails."""
        self._notify_error(PageFetcher.PAGE_ERROR, reason)

    # --- Internal helpers ---

    def _write_history(self, url):
        if url is None:
            return
        if self.history_position < len(self.history) - 1:
            self.history = self.history[:self.history_position + 1]
        self.history.append(url)
        self.history_position = len(self.history) - 1

    def _notify_ready(self):
        if self._on_page_ready:
            self._on_page_ready(self.page_data, self.page_meta)

    def _notify_error(self, code, message):
        self.page_error = (code, message)
        if self._on_page_error:
            self._on_page_error(code, message)

    @property
    def url_hash(self):
        """Return the destination hash of the current URL."""
        if self.current_url:
            parsed = self.parse_url(self.current_url)
            if parsed:
                return parsed[0]
        return None

    def disconnect(self):
        """Close any active link."""
        if self._link:
            try:
                self._link.teardown()
            except Exception:
                pass
            self._link = None
        self.status = PageFetcher.CONNECTION_CLOSED
