class EventDispatcher:
    def __init__(self):
        self._listeners = {}

    def subscribe(self, event_type, callback):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    def dispatch(self, event):
        if event.type in self._listeners:
            for callback in self._listeners[event.type]:
                callback(event)