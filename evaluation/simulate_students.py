import json
import hashlib
import numpy as np

def generate_dev_students(num_students=5, output_path="evaluation/datasets/dev/simulated_students_dev.json"):
    students = []
    
    # Pre-committed parameters
    topic_universe = ["DSA", "System Design", "Aptitude"]
    base_seed = 42
    
    # Beta(2,5) scaled by 100 for initial skill
    # Time uniform between 10 and 30 hours
    np.random.seed(base_seed)
    
    for i in range(num_students):
        student_id = f"sim_student_dev_{i+1}"
        student_seed = np.random.randint(0, 1000000)
        
        # Initial skills
        initial_skills = {}
        for t in topic_universe:
            # We use the seed for deterministic behavior per student, 
            # but setting the state here just for initialization
            initial_skills[t] = int(np.random.beta(2, 5) * 100)
            
        available_time = int(np.random.uniform(10, 30))
        
        students.append({
            "student_id": student_id,
            "student_seed": student_seed,
            "topic_universe": topic_universe,
            "initial_skills": initial_skills,
            "available_time": available_time,
            "parameters": {
                "skill_dist": "Beta(2,5)*100",
                "time_dist": "Uniform(10,30)",
                "priority_hours": {"High": 3, "Medium": 2, "Low": 1},
                "difficulty_dist": "Uniform(40,80)",
                "noise_dist": "Normal(0,5)",
                "skill_update_multiplier": 2.5,
                "mastery_threshold": 85,
                "struggle_threshold": 50
            },
            "simulation_model_version": "1.0"
        })
        
    with open(output_path, "w") as f:
        json.dump(students, f, indent=2)
        
    return students

if __name__ == "__main__":
    import os
    os.makedirs("evaluation/datasets/dev", exist_ok=True)
    generate_dev_students()
    print("Dev students generated.")
