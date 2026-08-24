import argparse
import json
import logging
import time
import hashlib
from pathlib import Path
import re

import pandas as pd
import numpy as np
from scipy.stats import wilcoxon

from app.config import settings
from app.llm.provider import get_provider
from app.rag.retriever import retrieve
from app.graph.workflow import build_graph
from evaluation.metrics.stats_utils import mcnemar_test
import matplotlib.pyplot as plt
from app.db.state.models import StudentProfile, PerformanceLog
from app.db.state.db import get_session

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def check_task_completion(task_type, response_text, turn_data, session_id):
    if task_type == "company_research":
        expected_facts = turn_data.get("expected_facts", [])
        if not expected_facts:
            return True
        for fact in expected_facts:
            # Simple string matching as used in Experiment 1 deterministic check
            if fact.lower() not in response_text.lower():
                return False
        return True
    
    elif task_type == "planner":
        try:
            # Check for JSON structure
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            else:
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start == -1 or end == -1:
                    return False
                json_str = response_text[start:end+1]
            parsed = json.loads(json_str)
            return isinstance(parsed, dict)
        except Exception:
            return False
            
    elif task_type == "progress":
        expected_topic = turn_data.get("expected_topic")
        expected_score = turn_data.get("expected_score")
        
        if not expected_topic or expected_score is None:
            return False
            
        # Check DB for symmetric evaluation of BOTH systems
        with get_session() as db:
            log = db.query(PerformanceLog).filter(PerformanceLog.student_id == session_id).order_by(PerformanceLog.timestamp.desc()).first()
            if not log:
                return False
            # Check if topic and score closely match what was expected
            if log.topic.lower() == expected_topic.lower() and log.score == expected_score:
                return True
        return False
    return False

def run_judge(user_msg, response_text, task_type):
    provider = get_provider()
    rubric_name = "plan_quality_rubric.md" if task_type == "planner" else "overall_quality_rubric.md"
    rubric_path = Path("evaluation/rubrics") / rubric_name
    
    if not rubric_path.exists():
        return "Rubric missing", 0
        
    rubric = rubric_path.read_text(encoding="utf-8")
    
    prompt = f"""You are an expert judge evaluating a university chatbot.
Score the following response on a 1-5 scale based on the provided rubric.

Rubric:
{rubric}

User Message:
{user_msg}

System Response:
{response_text}

Provide your justification first, then output a JSON block at the very end formatted EXACTLY like this:
{{"score": 5}}
where the score is an integer 1-5."""

    try:
        resp = provider.complete(prompt=prompt, temperature=0.0, use_cache=True)
        time.sleep(2) # rate limit mitigation
        score = 0
        if "```json" in resp.text:
            block = resp.text.split("```json")[-1].split("```")[0]
            score = json.loads(block).get("score", 0)
        elif "{" in resp.text:
            start = resp.text.rfind("{")
            end = resp.text.rfind("}")
            if start != -1 and end != -1:
                block = resp.text[start:end+1]
                score = json.loads(block).get("score", 0)
        return resp.text, score, prompt, rubric_name
    except Exception as e:
        logger.error(f"Judge failed: {e}")
        return str(e), 0, prompt, rubric_name

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True, help="Path to evaluation dataset")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        logger.error(f"Dataset not found: {dataset_path}")
        return

    dataset_bytes = dataset_path.read_bytes()
    dataset_sha256 = hashlib.sha256(dataset_bytes).hexdigest()
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    is_dev = "dev" in dataset_path.name
    dataset_version = "dev" if is_dev else dataset_path.stem

    logger.info(f"Loading dataset: {dataset_path} (SHA256: {dataset_sha256})")
    logger.info(f"Loaded {len(sessions)} sessions.")

    results = []
    judge_results = []
    
    provider = get_provider()
    prompt_template = Path("prompts/monolithic_baseline.txt").read_text(encoding="utf-8")
    
    for s_idx, session in enumerate(sessions):
        session_id = session["session_id"]
        logger.info(f"Processing Session {s_idx+1}/{len(sessions)}: {session_id}")
        
        # Init multi-agent
        graph = build_graph()
        thread_id = f"{session_id}_multi"
        config = {"configurable": {"thread_id": thread_id}}
        
        # Init monolithic
        monolithic_history = []
        
        for turn in session["turns"]:
            turn_id = turn["turn_id"]
            user_message = turn["user_message"]
            task_type = turn["task_type"]
            requires_retrieval = turn.get("requires_retrieval", False)
            
            logger.info(f"  Turn: {turn_id} | Task: {task_type}")
            
            # --- 1. MULTI-AGENT ---
            ma_start = time.perf_counter()
            ma_input = {"messages": [{"role": "user", "content": user_message}], "student_id": session_id}
            
            try:
                ma_state = graph.invoke(ma_input, config)
                ma_latency = (time.perf_counter() - ma_start) * 1000
                last_msg = ma_state["messages"][-1]
                ma_response = last_msg.content if hasattr(last_msg, "content") else last_msg.get("content", "")
                ma_tokens = 0 # Difficult to sum across nodes precisely without hooking callbacks, using 0 placeholder
                # Wait, we can get token usage if we iterate events, but `invoke` returns final state.
            except Exception as e:
                logger.error(f"Multi-agent crash: {e}")
                ma_response = ""
                ma_latency = 0
                ma_tokens = 0
                
            ma_completion = check_task_completion(task_type, ma_response, turn, session_id)
            
            # Rate limit mitigation for multi-agent (multiple calls happened inside graph)
            time.sleep(2)
            
            # --- 2. MONOLITHIC ---
            mono_start = time.perf_counter()
            context = ""
            if requires_retrieval:
                chunks = retrieve(query=user_message, collection_name="vitian_kb_fixed_size", top_k=settings.top_k_retrieval)
                context = "\n\n".join(c.text for c in chunks)
                
            history_str = ""
            for msg in monolithic_history:
                history_str += f"{msg['role']}: {msg['content']}\n"
                
            prompt = prompt_template.format(
                target_companies="General",
                skill_profile="None",
                available_time="1 month",
                context=context,
                history=history_str,
                user_message=user_message
            )
            
            try:
                mono_resp = provider.complete(prompt=prompt, temperature=0.0, use_cache=True)
                mono_latency = (time.perf_counter() - mono_start) * 1000
                mono_response = mono_resp.text
                mono_tokens = getattr(mono_resp, "usage_metadata", {}).get("total_tokens", 0)
                
                # Harness Progress State Updates for Monolithic
                if task_type == "progress":
                    if "progress_update" in mono_response:
                        try:
                            # Extract JSON block
                            start = mono_response.find("{")
                            end = mono_response.rfind("}")
                            if start != -1 and end != -1:
                                block = mono_response[start:end+1]
                                parsed = json.loads(block)
                                prog_data = parsed.get("progress_update", {})
                                topic = prog_data.get("topic")
                                score = prog_data.get("score")
                                if topic and score is not None:
                                    # Simulate the exact DB write
                                    with get_session() as db:
                                        profile = db.query(StudentProfile).filter(StudentProfile.student_id == session_id).first()
                                        if not profile:
                                            profile = StudentProfile(student_id=session_id, skill_profile={})
                                            db.add(profile)
                                        log = PerformanceLog(student_id=session_id, topic=topic, score=score, 
                                            is_struggle=score<50, is_mastery=score>=85)
                                        db.add(log)
                                        db.commit()
                        except Exception as e:
                            logger.error(f"Failed monolithic progress DB update: {e}")
                            
            except Exception as e:
                logger.error(f"Monolithic crash: {e}")
                mono_response = ""
                mono_latency = 0
                mono_tokens = 0

            mono_completion = check_task_completion(task_type, mono_response, turn, session_id)
            
            monolithic_history.append({"role": "user", "content": user_message})
            monolithic_history.append({"role": "assistant", "content": mono_response})
            
            time.sleep(2)
            
            # --- 3. JUDGING ---
            ma_judge_justification, ma_judge_score = "", 0
            mono_judge_justification, mono_judge_score = "", 0
            judge_prompt_used, rubric_used = "", ""
            
            # Judge only the first 5 sessions
            if s_idx < 5:
                ma_judge_justification, ma_judge_score, judge_prompt_used, rubric_used = run_judge(user_message, ma_response, task_type)
                mono_judge_justification, mono_judge_score, _, _ = run_judge(user_message, mono_response, task_type)
            
            results.append({
                "session_id": session_id,
                "turn_id": turn_id,
                "system": "multi_agent",
                "latency_ms": ma_latency,
                "tokens_used": ma_tokens,
                "task_completion": ma_completion,
                "quality_score": ma_judge_score,
                "dataset_version": dataset_version,
                "dataset_sha256": dataset_sha256
            })
            
            results.append({
                "session_id": session_id,
                "turn_id": turn_id,
                "system": "monolithic",
                "latency_ms": mono_latency,
                "tokens_used": mono_tokens,
                "task_completion": mono_completion,
                "quality_score": mono_judge_score,
                "dataset_version": dataset_version,
                "dataset_sha256": dataset_sha256
            })
            
            if s_idx < 5:
                judge_results.append({
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "system": "multi_agent",
                    "rubric": rubric_used,
                    "blinded": True,
                    "prompt": judge_prompt_used,
                    "justification": ma_judge_justification,
                    "score": ma_judge_score
                })
                judge_results.append({
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "system": "monolithic",
                    "rubric": rubric_used,
                    "blinded": True,
                    "prompt": judge_prompt_used,
                    "justification": mono_judge_justification,
                    "score": mono_judge_score
                })
            
    df = pd.DataFrame(results)
    
    Path("results").mkdir(exist_ok=True)
    out_csv = Path("results/experiment_3_raw.csv")
    df.to_csv(out_csv, index=False)
    
    if judge_results:
        pd.DataFrame(judge_results).to_csv("results/experiment_3_judge_justifications.csv", index=False)
    
    # Statistics
    ma_df = df[df["system"] == "multi_agent"].reset_index(drop=True)
    mono_df = df[df["system"] == "monolithic"].reset_index(drop=True)
    
    # Task Completion
    ma_comp = ma_df["task_completion"].tolist()
    mono_comp = mono_df["task_completion"].tolist()
    mcnemar_res = mcnemar_test(mono_comp, ma_comp)
    
    # Latency & Tokens
    try:
        lat_res = wilcoxon(mono_df["latency_ms"], ma_df["latency_ms"])
        lat_p = lat_res.pvalue
    except:
        lat_p = 1.0
        
    try:
        tok_res = wilcoxon(mono_df["tokens_used"], ma_df["tokens_used"])
        tok_p = tok_res.pvalue
    except:
        tok_p = 1.0
        
    # Quality Scores
    try:
        score_res = wilcoxon(mono_df["quality_score"], ma_df["quality_score"])
        score_p = score_res.pvalue
    except:
        score_p = 1.0
        
    stats_df = pd.DataFrame([{
        "metric": "task_completion",
        "sample_size": len(ma_df),
        "multi_agent": np.mean(ma_comp),
        "monolithic": np.mean(mono_comp),
        "test_statistic": mcnemar_res["test_statistic"],
        "p_value": mcnemar_res["p_value"],
        "significant": mcnemar_res["significant"]
    }, {
        "metric": "latency",
        "sample_size": len(ma_df),
        "multi_agent": ma_df["latency_ms"].mean(),
        "monolithic": mono_df["latency_ms"].mean(),
        "test_statistic": None,
        "p_value": lat_p,
        "significant": lat_p < 0.05
    }, {
        "metric": "quality_score",
        "sample_size": len(ma_df),
        "multi_agent": ma_df["quality_score"].mean(),
        "monolithic": mono_df["quality_score"].mean(),
        "test_statistic": None,
        "p_value": score_p,
        "significant": score_p < 0.05
    }])
    
    out_stats = Path("analysis/experiment_3_statistics.csv")
    out_stats.parent.mkdir(exist_ok=True)
    stats_df.to_csv(out_stats, index=False)
    
    logger.info("========================================")
    logger.info("EXPERIMENT 3 SUMMARY (DEV)")
    logger.info("========================================")
    logger.info(f"Total Evaluated Turns: {len(ma_df)}")
    logger.info(f"Multi-Agent Task Completion: {np.mean(ma_comp):.2f}")
    logger.info(f"Monolithic Task Completion : {np.mean(mono_comp):.2f}")
    logger.info(f"McNemar's p-value          : {mcnemar_res['p_value']:.4f} (Significant: {mcnemar_res['significant']})")
    logger.info("========================================")

if __name__ == "__main__":
    main()
