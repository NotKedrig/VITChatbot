import asyncio
from app.rag.ingest import ingest_documents

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    print("Ingesting fixed size chunks...")
    res1 = ingest_documents(chunking_strategy="fixed_size")
    print(res1)
