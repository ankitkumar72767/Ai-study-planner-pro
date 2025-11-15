"""
memory.py — Session memory and MemoryBank stub
"""
import datetime
from collections import defaultdict

class SessionMemory:
    def __init__(self):
        self._store = {}
        self._created_at = datetime.datetime.utcnow()

    def set(self, key, value):
        self._store[key] = value

    def get(self, key, default=None):
        return self._store.get(key, default)

    def delete(self, key):
        if key in self._store:
            del self._store[key]

class MemoryBank:
    """
    Simple long-term memory stub. Replace with DB or cloud storage for production.
    """
    def __init__(self):
        self._data = defaultdict(list)

    def add(self, user_id, record):
        self._data[user_id].append({"ts": datetime.datetime.utcnow().isoformat(), "record": record})

    def query(self, user_id):
        return list(self._data.get(user_id, []))