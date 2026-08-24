import json
import logging
import time
import argparse
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

from app.graph.state import AgentState
from app.agents.planner import planner_node
from app.db.state.db import get_session
from app.db.state.models import StudentProfile, PerformanceLog, PlanRevisionLog

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Pre-freeze deterministic interfaces
def get_addressable_draw(student_seed: int, topic: str, attempt_index: int, draw_type: str) -> float:
    """Returns a deterministic random float [0, 1) based on exact context."""
    h = hashlib.sha256(f"{student_seed}_{topic}_{attempt_index}_{draw_type}".encode()).hexdigest()
    # Convert first 8 bytes of hash to float [0, 1)
    return int(h[:16], 16) / (2**64 - 1)

def get_difficulty(student_seed: int, topic: str, attempt_index: int) -> float:
    draw = get_addressable_draw(student_seed, topic, attempt_index, "difficulty")
    return 40 + (draw * 40) # Uniform(40, 80)

def get_noise(student_seed: int, topic: str, attempt_index: int) -> float:
    draw = get_addressable_draw(student_seed, topic, attempt_index, "noise")
    # Simple approx of standard normal from uniform: using inverse transform sampling
    # or just Box-Muller. For simplicity and determinism, we'll use a direct approx.
    from scipy.stats import norm
    # Keep draw strictly within (0, 1)
    draw = max(1e-9, min(1 - 1e-9, draw))
    noise = norm.ppf(draw) * 5 # Normal(0, 5)
    return noise

def record_progress_deterministic(student_id: str, topic: str, score: int, is_adaptive: bool) -> str:
    """
    Bypasses LLM extraction entirely. 
    Writes to DB and returns the immediate progress signal.
    """
    is_struggle = score < 50
    is_mastery = score >= 85
    
    with get_session() as db:
        # DB setup
        profile = db.query(StudentProfile).filter(StudentProfile.student_id == student_id).first()
        if not profile:
            profile = StudentProfile(student_id=student_id, skill_profile={})
            db.add(profile)
            db.flush()
            
        new_log = PerformanceLog(
            student_id=student_id,
            topic=topic,
            score=score,
            is_struggle=is_struggle,
            is_mastery=is_mastery
        )
        db.add(new_log)
        db.flush()
        
        if is_adaptive:
            recent_logs = (
                db.query(PerformanceLog)
                .filter(PerformanceLog.student_id == student_id, PerformanceLog.topic == topic)
                .order_by(PerformanceLog.timestamp.desc())
                .limit(2)
                .all()
            )
            if len(recent_logs) == 2:
                if all(log.is_struggle for log in recent_logs):
                    return "struggle"
                elif all(log.is_mastery for log in recent_logs):
                    return "mastery"
                    
    return "none"


def run_simulation_condition(student: dict, is_adaptive: bool, initial_plan: dict):
    student_id = f"{student['student_id']}_{'adaptive' if is_adaptive else 'static'}"
    student_seed = student["student_seed"]
    
    # Initialize state
    latent_skills = dict(student["initial_skills"])
    available_time = student["available_time"]
    
    # Trackers
    attempts = {t: 0 for t in student["topic_universe"]}
    time_to_competency_hours = {t: None for t in student["topic_universe"]}
    total_scores = []
    
    current_plan = initial_plan
    hours_spent = 0
    
    # Simulation loop
    while available_time > 0 and current_plan.get("tasks"):
        # Pop the first task
        task = current_plan["tasks"][0]
        topic = task["topic"]
        priority = task["priority"]
        
        # Priority mapping
        hours_allocated = {"High": 3, "Medium": 2, "Low": 1}.get(priority, 1)
        
        # Cap by available time
        hours_spent_on_task = min(hours_allocated, available_time)
        available_time -= hours_spent_on_task
        hours_spent += hours_spent_on_task
        
        # Remove completed task (unless it's the last one, to avoid empty plan edge cases in POC)
        if len(current_plan["tasks"]) > 1:
            current_plan["tasks"].pop(0)
            
        # If topic is not in universe, skip (edge case handling)
        if topic not in latent_skills:
            continue
            
        # Attempt!
        idx = attempts[topic]
        attempts[topic] += 1
        
        diff = get_difficulty(student_seed, topic, idx)
        noise = get_noise(student_seed, topic, idx)
        
        # Skill update happens BEFORE the test for this task
        latent_skills[topic] += (hours_spent_on_task * student["parameters"]["skill_update_multiplier"])
        
        # Bounded score
        raw_score = latent_skills[topic] - (diff - 50) + noise
        score = int(max(0, min(100, raw_score)))
        total_scores.append(score)
        
        if score >= 85 and time_to_competency_hours[topic] is None:
            time_to_competency_hours[topic] = hours_spent
            
        # Process deterministic signal
        signal = record_progress_deterministic(student_id, topic, score, is_adaptive)
        
        if is_adaptive and signal in ["struggle", "mastery"]:
            # Deterministic Replanning
            state = AgentState({
                "student_id": student_id,
                "current_plan": current_plan,
                "progress_signal": signal,
                "affected_topic": topic
            })
            result = planner_node(state)
            current_plan = result.get("current_plan", current_plan)

    # Calculate metrics for this condition
    mastery_count = sum(1 for t, v in time_to_competency_hours.items() if v is not None)
    topic_mastery_rate = mastery_count / len(student["topic_universe"])
    
    # Time to competency (average of achieved, or penalty max time 30 if not achieved)
    ttc_list = [v if v is not None else 30 for v in time_to_competency_hours.values()]
    avg_ttc = np.mean(ttc_list)
    
    problem_solving_success_rate = np.mean(total_scores) if total_scores else 0
    
    # Weak topic improvement (topics that started < 50, how many reached >=85)
    weak_starts = [t for t, s in student["initial_skills"].items() if s < 50]
    weak_improved = sum(1 for t in weak_starts if time_to_competency_hours[t] is not None)
    weak_improvement_rate = weak_improved / len(weak_starts) if weak_starts else 1.0
    
    with get_session() as db:
        replanning_events_count = db.query(PlanRevisionLog).filter(PlanRevisionLog.student_id == student_id).count()
        
    return {
        "student_id": student["student_id"],
        "condition": "adaptive" if is_adaptive else "static",
        "topic_mastery_rate": topic_mastery_rate,
        "time_to_competency": avg_ttc,
        "problem_solving_success_rate": problem_solving_success_rate,
        "weak_topic_improvement": weak_improvement_rate,
        "replanning_events_count": replanning_events_count
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset)
    sha256 = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    
    with open(dataset_path, "r") as f:
        students = json.load(f)
        
    results = []
    
    # Single LLM pass for initial plans
    for student in students:
        logger.info(f"Generating initial plan for {student['student_id']}")
        init_state = AgentState({
            "student_id": student["student_id"],
            "skill_profile": student["initial_skills"],
            "available_time": f"{student['available_time']} hours"
        })
        
        # The ONLY LLM call required per student
        planner_result = planner_node(init_state)
        initial_plan = planner_result.get("current_plan")
        
        if not initial_plan or not initial_plan.get("tasks"):
            logger.error(f"Failed to generate initial plan for {student['student_id']}. Skipping.")
            continue
            
        # 1. Static Execution
        logger.info(f"Running STATIC condition for {student['student_id']}")
        # Deep copy plan to avoid mutation
        static_plan = json.loads(json.dumps(initial_plan))
        res_static = run_simulation_condition(student, False, static_plan)
        res_static["dataset_version"] = dataset_path.name
        res_static["dataset_sha256"] = sha256
        res_static["simulation_model_version"] = student["simulation_model_version"]
        results.append(res_static)
        
        # 2. Adaptive Execution
        logger.info(f"Running ADAPTIVE condition for {student['student_id']}")
        adaptive_plan = json.loads(json.dumps(initial_plan))
        res_adaptive = run_simulation_condition(student, True, adaptive_plan)
        res_adaptive["dataset_version"] = dataset_path.name
        res_adaptive["dataset_sha256"] = sha256
        res_adaptive["simulation_model_version"] = student["simulation_model_version"]
        results.append(res_adaptive)
        
    df = pd.DataFrame(results)
    if "dev" not in dataset_path.name.lower():
        import os
        os.makedirs("results", exist_ok=True)
        df.to_csv("results/experiment_5_raw.csv", index=False)
        logger.info("Saved final results to results/experiment_5_raw.csv")
    else:
        logger.info("Dev run complete. Output:")
        print(df)

if __name__ == "__main__":
    main()
