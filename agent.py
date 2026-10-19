"""
NovaTech Customer Support AI Agent (agent.py)
Framework-free ReAct Agent with Function Calling, Read-Only SQLite, Date Difference, and FAISS RAG.
"""

import os
import sys
import json
import random
import sqlite3
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

def load_env_file():
    """Load key-value pairs from .env file into os.environ if not already present."""
    search_paths = [
        ".env",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join("..", ".env"),
    ]
    for p in search_paths:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k not in os.environ:
                            os.environ[k] = v
            break

load_env_file()
FLAKY = "--flaky" in sys.argv

TRACE_LOG_PATH = "trace.log"
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set. Please add it to your .env file or environment.")

client = Groq(api_key=GROQ_API_KEY)
LLM_MODEL_NAME = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

def log_trace(message: str):
    """
    Helper to log every step to a file named trace.log and print to stdout.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    print(f"[TRACE] {message}")

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer






DOCS_DIR = "novatech_docs"
if not os.path.exists(DOCS_DIR):
    script_dir_docs = os.path.join(os.path.dirname(os.path.abspath(__file__)), "novatech_docs")
    if os.path.exists(script_dir_docs):
        DOCS_DIR = script_dir_docs
    elif os.path.exists(os.path.join("..", "novatech_docs")):
        DOCS_DIR = os.path.join("..", "novatech_docs")

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

def load_and_chunk(docs_dir: str, chunk_size: int, overlap: int):
    chunks = []
    if not os.path.exists(docs_dir):
        return chunks
    for fname in sorted(os.listdir(docs_dir)):
        fpath = os.path.join(docs_dir, fname)
        if os.path.isfile(fpath) and fname.lower().endswith((".md", ".txt")):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            start = 0
            while start < len(content):
                end = min(start + chunk_size, len(content))
                chunks.append({"text": content[start:end], "source": fname})
                if end == len(content):
                    break
                start += (chunk_size - overlap)
    return chunks

def build_vector_store(chunks):
    if not chunks:
        # Create an empty index if no chunks
        return faiss.IndexFlatL2(384)
    texts = [c["text"] for c in chunks]
    embeddings = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    return index








active_chunks = load_and_chunk(DOCS_DIR, chunk_size=500, overlap=50)
active_index = build_vector_store(active_chunks)

def base_search_policies(question: str, k: int = 3) -> str:
    if active_index.ntotal == 0 or not active_chunks:
        return "No policy documents found."
    q_emb = embedder.encode([question], convert_to_numpy=True)
    distances, indices = active_index.search(q_emb, k)
    results = []
    for idx in indices[0]:
        if idx < len(active_chunks):
            c = active_chunks[idx]
            results.append(f"Source: {c['source']}\nText: {c['text']}")
    return "\n\n".join(results)









def query_database(sql: str = None, **kwargs) -> str:
    """
    Connect to novatech_store.db using sqlite3 in strictly read-only mode.
    CRITICAL REQUIREMENT: Enforces URI 'file:novatech_store.db?mode=ro', uri=True.
    Executes the SQL query and returns the results as a string.
    """
    query = sql or kwargs.get("query")
    if not query:
        raise ValueError("query_database requires a 'sql' query parameter.")






    conn = sqlite3.connect('file:novatech_store.db?mode=ro', uri=True)
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        if cursor.description is None:
            return "Query executed successfully. No rows returned."
        columns = [d[0] for d in cursor.description]
        if not rows:
            return "No results found."
        results = [dict(zip(columns, row)) for row in rows]
        if len(results) > 50:
            return json.dumps(results[:50], default=str, indent=2) + f"\n[Output truncated: showing 50 of {len(results)} rows]"
        return json.dumps(results, default=str, indent=2)
    finally:
        conn.close()






def calculate_days(date1: str = None, date2: str = None, **kwargs) -> int:
    """
    Takes two ISO date strings, calculates the difference using Python's datetime,
    and returns the integer difference in days.
    """
    d1_str = date1 or kwargs.get("date_1") or kwargs.get("start_date") or kwargs.get("d1")
    d2_str = date2 or kwargs.get("date_2") or kwargs.get("end_date") or kwargs.get("d2")
    if not d1_str or not d2_str:
        raise ValueError(f"calculate_days requires two ISO date strings (date1, date2). Received: {kwargs}")

    d1 = datetime.fromisoformat(str(d1_str).strip()[:10]).date()
    d2 = datetime.fromisoformat(str(d2_str).strip()[:10]).date()
    return abs((d2 - d1).days)


def search_policies(question: str = None, **kwargs) -> str:
    """
    Searches NovaTech policy documents using RAG vector search.
    Flaky Mode: If --flaky is enabled, randomly raises Exception 30% of the time.
    """
    q = question or kwargs.get("query") or kwargs.get("search_query")
    if not q:
        raise ValueError("search_policies requires a 'question' parameter.")

    global FLAKY
    is_flaky = FLAKY or ("--flaky" in sys.argv)
    if is_flaky and random.random() < 0.30:
        raise Exception("Database timeout - search failed")

    return base_search_policies(q)






AVAILABLE_TOOLS = {
    "query_database": query_database,
    "calculate_days": calculate_days,
    "search_policies": search_policies,
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Execute a strictly read-only SQL query against novatech_store.db to inspect customers, products, orders, order items, or returns. Returns formatted JSON string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL query to execute (must be a SELECT statement)."
                    }
                },
                "required": ["sql"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_days",
            "description": "Calculates the difference in days between two ISO date strings (e.g. 'YYYY-MM-DD'). Useful for comparing delivery dates with today or order dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date1": {
                        "type": "string",
                        "description": "The first ISO date string (YYYY-MM-DD)."
                    },
                    "date2": {
                        "type": "string",
                        "description": "The second ISO date string (YYYY-MM-DD)."
                    }
                },
                "required": ["date1", "date2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_policies",
            "description": "Searches NovaTech company policy documents using semantic search. Use for questions regarding returns, warranty, refunds, shipping, delivery, cancellations, loyalty program, or store policies.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The search query or policy question."
                    }
                },
                "required": ["question"]
            }
        }
    }
]







def run_agent(user_query: str, max_iterations: int = 10) -> str:
    """
    Executes a ReAct-style while-loop with function calling.
    - Max 10 iterations to prevent infinite loops.
    - System prompt defines role, date (2026-10-18), database schema, and retry strategy.
    - Logs each step to trace.log (before and after execution).
    - If a tool fails (e.g. flaky timeout), catches it and passes stringified error to the LLM to retry.
    """
    system_prompt = (
        "Today is 2026-10-18. You are a NovaTech customer support agent. "
        "You have tools to query the read-only database, calculate dates, and search policies. "
        "If a tool fails, you MUST retry or adapt your strategy instead of giving up.\n\n"
        "Database Schema (novatech_store.db):\n"
        "- customers(customer_id TEXT PK, full_name TEXT, email TEXT, city TEXT, joined_date TEXT)\n"
        "- products(product_id TEXT PK, name TEXT, category TEXT, list_price_jod REAL)\n"
        "- orders(order_id TEXT PK, customer_id TEXT FK, order_date TEXT, delivered_date TEXT, status TEXT, payment_method TEXT, total_jod REAL)\n"
        "- order_items(order_id TEXT FK, product_id TEXT FK, quantity INTEGER, unit_price_jod REAL)\n"
        "- returns(order_id TEXT FK, return_date TEXT, reason TEXT)\n\n"
        "All money is in Jordanian dinars (JOD). All dates are YYYY-MM-DD text.\n"
        "Instructions:\n"
        "1. Always query the database to verify order, customer, or product facts before answering.\n"
        "2. Check store policies using search_policies for policy rules, return windows, fees, and exceptions.\n"
        "3. Use calculate_days to verify the number of days between dates (such as delivered_date and today 2026-10-18).\n"
        "4. If a tool call fails, inspect the error, retry, or adjust your query.\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_query}
    ]

    log_trace(f"=== NEW AGENT SESSION ===")
    log_trace(f"USER QUERY: {user_query}")

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        log_trace(f"--- Iteration {iteration}/{max_iterations} ---")

        response = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=messages,
            tools=TOOLS_SCHEMA,
            tool_choice="auto"
        )

        choice = response.choices[0]
        response_message = choice.message
        if response_message.tool_calls:
            messages.append(response_message)
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                call_id = tool_call.id
                raw_args = tool_call.function.arguments

                # Parse tool arguments safely
                try:
                    tool_args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except Exception as parse_err:
                    tool_args = {}
                log_trace(f"TOOL CALL: {tool_name} | ARGS: {json.dumps(tool_args)}")
                try:
                    if tool_name not in AVAILABLE_TOOLS:
                        raise ValueError(f"Unknown tool: '{tool_name}'")

                    tool_fn = AVAILABLE_TOOLS[tool_name]
                    result = tool_fn(**tool_args)
                    result_str = str(result)

                    log_trace(f"TOOL RESULT: {tool_name} | SUCCESS:\n{result_str}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": result_str
                    })

                except Exception as err:
                    error_str = f"Error: {str(err)}"

                    log_trace(f"TOOL ERROR: {tool_name} | FAILURE: {error_str}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tool_name,
                        "content": error_str
                    })

        else:
            final_answer = response_message.content or ""
            log_trace(f"FINAL ANSWER:\n{final_answer}")
            print("\n" + "=" * 30 + " AGENT RESPONSE " + "=" * 30)
            print(final_answer)
            print("=" * 76 + "\n")
            return final_answer

    fallback_msg = "Agent stopped: Maximum iterations (10) reached without a final text response."
    log_trace(fallback_msg)
    print(fallback_msg)
    return fallback_msg


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NovaTech Customer Support ReAct AI Agent")
    parser.add_argument("query", nargs="?", default=None, help="Customer support question")
    parser.add_argument("--flaky", action="store_true", help="Enable 30%% flaky failure rate on search_policies")
    args, unknown = parser.parse_known_args()

    if args.flaky:
        FLAKY = True
        log_trace("Flaky mode ENABLED: search_policies has a 30% random failure rate.")

    if args.query:
        user_query = args.query
    else:
        try:
            user_query = input("Enter customer inquiry (press Enter for sample query): ").strip()
        except (EOFError, KeyboardInterrupt):
            user_query = ""

        if not user_query:
            user_query = "Can customer C001 return order NT-10560? Today is 2026-10-18."
            print(f"No query provided. Running default sample query:\n\"{user_query}\"\n")

    run_agent(user_query)
