"""
tools.py — Planner tool and helpers
"""
from dateutil import parser
from datetime import datetime, timedelta
from agent.utils import week_days
import math

class PlannerTool:
    def __init__(self, logger=None, memory=None):
        self.logger = logger
        self.memory = memory

    def create_schedule(self, profile):
        # profile keys: subjects (list), weekly_hours (int), priority (dict), deadlines (dict)
        subjects = profile.get("subjects", [])
        total_hours = profile.get("weekly_hours", 10)
        priority = profile.get("priority", {})
        # Normalize priority
        pvals = [priority.get(s, 1/len(subjects)) for s in subjects]
        s = sum(pvals) if sum(pvals)>0 else len(subjects)
        weights = [pv/s for pv in pvals]

        # Distribute hours across 7 days
        hours_per_subject = {subjects[i]: max(0.5, round(weights[i]*total_hours,1)) for i in range(len(subjects))}
        schedule = {}
        start_date = datetime.utcnow()
        for d in week_days():
            day_blocks = []
            for subj, hrs in hours_per_subject.items():
                # split into 1-2 hour blocks
                blocks = int(max(1, round(hrs/1.5)))
                for bi in range(blocks):
                    start = (start_date + timedelta(days=0)).replace(hour=9+bi%8, minute=0)
                    end = start + timedelta(hours=min(2, hrs))
                    day_blocks.append({"subject": subj, "hours": round(hrs/blocks,2), "start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")})
            schedule[d] = day_blocks
        # Save to memory if provided
        if self.memory:
            self.memory.add(profile.get("name","anon"), {"schedule": schedule})
            if self.logger:
                self.logger.info("Schedule saved to MemoryBank")
        return schedule
