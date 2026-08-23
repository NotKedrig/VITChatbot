import json
from app.rag.retriever import retrieve
from app.config import settings

with open("evaluation/datasets/dev/rag_questions_dev.json") as f:
    qs = json.load(f)

with open("raw_results_clean.json") as f:
    results = json.load(f)

for q in qs:
    qid = q["question_id"]
    if qid == "dev_010": continue
    print(f"=== {qid} ===")
    print(f"Q: {q['question']}")
    print(f"Gold: {q['expected_facts']}")
    
    # Get retrieved chunks
    chunks = retrieve(q['question'], collection_name="vitian_kb_fixed_size", top_k=settings.top_k_retrieval, embedding_model_name=settings.embedding_model_name)
    print("RETRIEVED CHUNKS:")
    for i, c in enumerate(chunks):
        print(f"  [{i+1}] {c.doc_id}: {c.text[:100]}...")
    
    # Get answers
    vanilla = [r for r in results if r["question_id"] == qid and r["system"] == "Vanilla"][0]
    rag = [r for r in results if r["question_id"] == qid and r["system"] == "RAG"][0]
    
    print(f"Vanilla Ans: {vanilla['answer'][:100]}...")
    print(f"Vanilla Fact: {vanilla['factual_accuracy']}, Halluc: {vanilla['hallucinated']}")
    print(f"RAG Ans: {rag['answer'][:100]}...")
    print(f"RAG Fact: {rag['factual_accuracy']}, Halluc: {rag['hallucinated']}")
    print()
