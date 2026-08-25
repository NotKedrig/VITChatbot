import requests
import json
import time

def test_chat(message: str, expected_node: str):
    url = "http://127.0.0.1:8000/api/chat"
    payload = {
        "message": message,
        "student_id": "demo_student",
        "thread_id": f"test_thread_{int(time.time())}"
    }
    
    print(f"\n--- Testing: '{message}' ---")
    try:
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Determine which node was actually hit
        # The node before 'END' is usually the final agent executed.
        metadata = data.get("runtime_metadata", [])
        
        # supervisor is usually at index 0, the worker is at index 1
        worker_node = "unknown"
        if len(metadata) > 1:
            worker_node = metadata[1].get("node", "unknown")
        elif len(metadata) == 1:
            worker_node = metadata[0].get("node", "unknown")
            
        print(f"Reply: {data.get('reply')}")
        print(f"Worker Node Executed: {worker_node}")
        
        if worker_node == expected_node:
            print(f"✅ PASS (Expected: {expected_node}, Got: {worker_node})")
        else:
            print(f"❌ FAIL (Expected: {expected_node}, Got: {worker_node})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test cases as per the verification plan
    test_cases = [
        ("how to make dosa", "out_of_scope"),
        ("what are Meridian's eligibility requirements?", "company_research"),
        ("create a 3-week DSA plan for Amazon", "planner"),
        ("I scored 40% in DSA", "progress"),
        ("remind me to practice DSA tomorrow at 7 PM", "notification")
    ]
    
    for msg, exp in test_cases:
        test_chat(msg, exp)
        time.sleep(1) # tiny sleep to avoid rate limits / overlap

