"""
observability.py — lightweight Logger and Trace helpers
"""
import logging
from datetime import datetime

class Logger:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        self._lg = logging.getLogger("StudyPlannerAgent")

    def info(self, msg):
        self._lg.info(msg)

    def error(self, msg):
        self._lg.error(msg)

    def debug(self, msg):
        self._lg.debug(msg)

class Trace:
    _traces = {}

    @classmethod
    def start_trace(cls, trace_id):
        cls._traces[trace_id] = {"start": datetime.utcnow().isoformat(), "events": []}

    @classmethod
    def log_event(cls, trace_id, event):
        if trace_id in cls._traces:
            cls._traces[trace_id]["events"].append({"ts": datetime.utcnow().isoformat(), "event": event})

    @classmethod
    def end_trace(cls, trace_id):
        if trace_id in cls._traces:
            cls._traces[trace_id]["end"] = datetime.utcnow().isoformat()
            # For demo, print summary
            print("\nTRACE SUMMARY:", json_safe(cls._traces[trace_id]))

def json_safe(obj):
    import json
    return json.dumps(obj, indent=2, default=str)
