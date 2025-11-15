"""
main_agent.py — Minimal ADK-style Study Planner Agent (demo-mode)
This file demonstrates:
- session memory
- a planner tool
- observability hooks
Run: python -m agent.main_agent --demo
"""
import argparse
import time
from agent.memory import SessionMemory, MemoryBank
from agent.tools import PlannerTool
from agent.observability import Logger, Trace

def build_agent():
    logger = Logger()
    session = SessionMemory()
    memory_bank = MemoryBank()  # stub persistent storage
    planner = PlannerTool(logger=logger, memory=memory_bank)
    return dict(logger=logger, session=session, memory_bank=memory_bank, planner=planner)

def run_demo():
    env = build_agent()
    logger = env["logger"]
    session = env["session"]
    planner = env["planner"]

    logger.info("Starting Study Planner Agent (demo)")
    Trace.start_trace("demo-session")
    # Simulated conversation
    user_profile = {
        "name": "Student",
        "subjects": ["Math", "Algorithms", "DBMS"],
        "weekly_hours": 20,
        "deadlines": {"Math": "2025-12-10", "DBMS": "2025-11-30"},
        "priority": {"Math": 0.5, "Algorithms": 0.3, "DBMS": 0.2}
    }
    session.set("profile", user_profile)
    logger.info("User profile saved in session")

    # Planner tool usage
    schedule = planner.create_schedule(user_profile)
    logger.info("Schedule created")
    print("\n=== GENERATED WEEKLY PLAN ===")
    for day, blocks in schedule.items():
        print(f"\n{day}:")
        for b in blocks:
            print(f" - {b['start']} to {b['end']}: {b['subject']} ({b['hours']} hrs)")

    Trace.end_trace("demo-session")
    logger.info("Demo finished")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Run demo")
    args = parser.parse_args()
    if args.demo:
        run_demo()
    else:
        print("Run with --demo to execute a demo.")