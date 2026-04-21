from typing import Callable


class DispachMixin:
    _LISTENERS: list[tuple[Callable, str]] = []

    def on_event(self, name: str, old_entity, new_entity):
        self.ensure_one()
        for listener, listener_name in self._LISTENERS:
            if listener_name == name:
                listener(self, old_entity, new_entity)
