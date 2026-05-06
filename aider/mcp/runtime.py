"""Sync wrapper around the async Manager.

Aider's REPL is synchronous; the MCP Manager and the SDK underneath are
asyncio-based. Spinning up a fresh event loop per call would tear down
and re-spawn server subprocesses each time — too slow, and it undoes the
warm-loop assumption the streaming tool-call path relies on.

`MCPRuntime` runs a single asyncio loop on a daemon thread for the life
of the aider session. Sync callers submit coroutines via
`asyncio.run_coroutine_threadsafe` and block on the resulting future;
exceptions propagate unchanged."""

import asyncio
import threading


class MCPRuntime:
    def __init__(self, manager):
        self.manager = manager
        self._loop = None
        self._thread = None
        self._started = False

    def start(self):
        """Spin up the loop thread and block until manager.start_all completes.
        Idempotent: a second call returns immediately."""
        if self._started:
            return
        self._loop = asyncio.new_event_loop()
        ready = threading.Event()

        def _run():
            asyncio.set_event_loop(self._loop)
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True, name="mcp-runtime")
        self._thread.start()
        ready.wait()
        self._submit(self.manager.start_all())
        self._started = True

    def stop(self):
        """Shut down servers and stop the loop. Safe to call before start()
        and multiple times in a row — atexit hooks rely on this."""
        if not self._started:
            return
        try:
            self._submit(self.manager.stop_all())
        except Exception:
            # Don't mask the shutdown signal with cleanup errors.
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        try:
            self._loop.close()
        except Exception:
            pass
        self._loop = None
        self._thread = None
        self._started = False

    def list_servers(self):
        """Sync passthrough — Manager.list_servers is already sync because
        it just snapshots in-memory state."""
        return self.manager.list_servers()

    def list_tools(self, server=None):
        return self._submit(self.manager.list_tools(server=server))

    def call_tool(self, server, name, arguments):
        return self._submit(self.manager.call_tool(server, name, arguments))

    def restart(self, server_name):
        return self._submit(self.manager.restart(server_name))

    def get_server_config(self, server):
        """Read-only access to a server's normalized mcp.yml config (with
        default_permission/permissions defaulted). Returns None if the
        server isn't configured."""
        return self.manager.servers_config.get(server)

    def get_tool_meta(self, server, tool_name):
        """Look up one tool's metadata dict (with annotations) from a
        running server. Returns None if the server isn't running or the
        tool isn't exposed. Sync wrapper around list_tools."""
        try:
            tools = self.list_tools(server=server)
        except Exception:
            return None
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool
        return None

    def _submit(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()
