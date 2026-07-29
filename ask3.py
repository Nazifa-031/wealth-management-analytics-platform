"""
Step 3: Ask - Hybrid RAG + Analytical Query Engine

Two paths:
  1. Analytical questions (Top N, highest, lowest, total, average, count,
     rankings) are answered by analytics.py, which aggregates over the
     FULL mart dataset fetched from the API. This matches Databricks SQL
     output exactly, since it is not limited by similarity search sample size.
  2. Descriptive/summary questions (e.g. "summarize client X", "how is
     scheme Y doing") go through RAG: embed the question, retrieve the
     most relevant chunks from ChromaDB (filtered by mart when detectable),
     then ask the LLM to answer using only that retrieved context.
  3. Report requests ("generate a report for X") are detected separately
     and produce an HTML file via report_utils.py. The mart (client,
     advisor, scheme, amc, or executive) is detected with the same
     analytics.detect_mart() used for analytical routing, so report
     requests aren't limited to clients anymore.
"""

import os
import re
import logging
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

import analytics
import report_utils

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
CHROMA_DIR = "chroma_store"
COLLECTION_NAME = "client_portfolios"
TOP_K = 15

PROMPT_TEMPLATE = """You are a data assistant for a wealth management company.
Answer STRICTLY using only the DATA provided below.

Rules:
1. If the answer is not in the data, say exactly: "I don't have enough data to answer that."
2. Do not invent numbers, names, dates, or percentages not present in the data.
3. Quote figures exactly as given.
4. If the data seems incomplete for the question, say so rather than guessing.

--- DATA ---
{context}
--- END DATA ---

Question: {question}

Answer using only the data above:"""

REPORT_TRIGGER_PATTERNS = [
    r"generate\s+(a\s+)?report",
    r"create\s+(a\s+)?report",
    r"report\s+for",
    r"investment\s+report",
    r"summary\s+report",
]

# Report request routing (mart detection + target extraction) now lives in
# report_utils.parse_report_request(), shared with the 04_generate_report.py
# CLI so both understand identical phrasing.


def is_report_request(question):
    q = question.lower()
    return any(re.search(p, q) for p in REPORT_TRIGGER_PATTERNS)


def handle_report(question):
    try:
        path = report_utils.generate_report_from_text(question)
        return f"Report generated: {path}\nOpen this file in a browser to view it."
    except ValueError as e:
        return str(e)


def handle_analytical(question):
    answer, debug = analytics.answer_analytical(question)
    logger.info(f"[ANALYTICS] {debug}")
    return answer


def detect_mart_filter(question):
    mart = analytics.detect_mart(question)
    return {"mart": mart} if mart else None


def retrieve(question, model, collection, top_k=TOP_K):
    query_embedding = model.encode([question]).tolist()
    where_filter = detect_mart_filter(question)
    if where_filter:
        logger.info(f"[RAG] filtering by mart: {where_filter['mart']}")

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k,
        where=where_filter,
    )
    documents = results.get("documents", [[]])[0]
    logger.info(f"[RAG] retrieved {len(documents)} chunks")
    return documents


def ask_llm(prompt):
    if LLM_PROVIDER == "gemini":
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        return response.text
    else:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


def handle_rag(question, model, collection):
    chunks = retrieve(question, model, collection)
    if not chunks:
        return "I don't have enough data to answer that."
    context = "\n\n".join(chunks)
    prompt = PROMPT_TEMPLATE.format(context=context, question=question)
    return ask_llm(prompt)


def main():
    print("Loading embedding model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    print("Connecting to ChromaDB...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME)

    print("Ready. Type 'quit' to exit.")

    while True:
        question = input("\nQuestion: ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if not question:
            continue

        try:
            if is_report_request(question):
                logger.info("[ROUTE] report generation")
                answer = handle_report(question)
            elif analytics.is_analytical(question) or re.search(r"client\s*(?:id\s*)?\d+", question.lower()):
                logger.info("[ROUTE] analytical (exact computation)")
                answer = handle_analytical(question)
                if answer is None:
                    logger.info("[ROUTE] analytical path declined, falling back to RAG")
                    answer = handle_rag(question, model, collection)
            else:
                logger.info("[ROUTE] RAG (descriptive)")
                answer = handle_rag(question, model, collection)

            print("\n" + answer)

        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()