"""Global hotkeys via RegisterHotKey + Qt native event filter. Observes keys only."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication

from pi_tool.platform import win32

_MSG_TYPES = (b"windows_generic_MSG", b"windows_dispatcher_MSG")


class HotkeyManager(QAbstractNativeEventFilter):
    def __init__(self) -> None:
        super().__init__()
        self._callbacks: dict[int, Callable[[], None]] = {}
        self._next_id = 0xB000
        app = QCoreApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)

    def register(self, spec: str, callback: Callable[[], None]) -> bool:
        """False if the combination is taken by another app or we're not on Windows."""
        mods, vk = win32.parse_hotkey(spec)
        hk_id = self._next_id
        self._next_id += 1
        if not win32.register_hotkey(hk_id, mods, vk):
            return False
        self._callbacks[hk_id] = callback
        return True

    def unregister_all(self) -> None:
        for hk_id in self._callbacks:
            win32.unregister_hotkey(hk_id)
        self._callbacks.clear()

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) in _MSG_TYPES:
            hk = win32.hotkey_id_from_msg(int(message))
            if hk in self._callbacks:
                self._callbacks[hk]()
                return True, 0
        return False, 0
