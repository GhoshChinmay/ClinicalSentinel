"""
ClinicalSentinel — RegRAG Engine (Feature F4)
Retrieval-Augmented Regulatory Compliance Auto-Checker.
Cross-references detected clinical data anomalies against a ChromaDB vector store
containing ICH E6(R3), 21 CFR Part 11, and the DPDP Act 2023.
"""

import os
import json
from utils import logger, _BACKEND_DIR

try:
    import chromadb
    from langchain_groq import ChatGroq
    try:
        # Prefer the new, non-deprecated package
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError:
        from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore[no-redef]
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.prompts import PromptTemplate
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# Initialize Paths and DB
_VECTOR_DB_DIR = os.path.join(_BACKEND_DIR, "data", "chroma_db")
_REGULATIONS_DIR = os.path.join(_BACKEND_DIR, "data", "regulations")

if RAG_AVAILABLE:
    os.makedirs(_VECTOR_DB_DIR, exist_ok=True)
    os.makedirs(_REGULATIONS_DIR, exist_ok=True)
    
    # Initialize ChromaDB Persistent Client
    chroma_client = chromadb.PersistentClient(path=_VECTOR_DB_DIR)
    
    # Use a lightweight, fast, local embedding model
    embedding_fn = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def initialize_regulatory_knowledge_base():
    """
    Reads regulatory text files (e.g., FDA_21_CFR_Part_11.txt) from the regulations 
    directory, chunks them, and stores them in the vector database.
    """
    if not RAG_AVAILABLE:
        logger.warning("RAG dependencies missing. Run: pip install chromadb langchain-groq sentence-transformers")
        return

    collection_name = "clinical_regulations"
    
    # Check if we already have data
    existing_collections = [c.name for c in chroma_client.list_collections()]
    if collection_name in existing_collections:
        collection = chroma_client.get_collection(collection_name)
        if collection.count() > 0:
            logger.info("Regulatory Knowledge Base already initialized.")
            return collection
            
    logger.info("Initializing Regulatory Knowledge Base...")
    collection = chroma_client.create_collection(collection_name)
    
    # Find all .txt files in the regulations folder
    reg_files = [f for f in os.listdir(_REGULATIONS_DIR) if f.endswith(".txt")]
    
    if not reg_files:
        logger.warning(f"No regulatory text files found in {_REGULATIONS_DIR}. Please add ICH E6 / 21 CFR Part 11 documents.")
        return collection
        
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    
    for filename in reg_files:
        filepath = os.path.join(_REGULATIONS_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
            
        chunks = text_splitter.split_text(text)
        
        # Convert chunks to embeddings and store in Chroma
        embeddings = embedding_fn.embed_documents(chunks)
        ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": filename} for _ in chunks]
        
        collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Indexed {len(chunks)} clauses from {filename}.")
        
    return collection


def evaluate_compliance(investigator_id: str, anomaly_details: dict) -> dict:
    """
    Takes an investigator's flagged anomalies, queries the regulatory vector DB 
    for relevant laws, and uses Groq to generate a compliance verdict.
    """
    if not RAG_AVAILABLE:
        return {"error": "RAG dependencies not installed."}
        
    collection = initialize_regulatory_knowledge_base()
    if collection.count() == 0:
        return {"error": "No regulatory documents indexed in the Vector DB."}
        
    logger.info(f"Evaluating Regulatory Compliance for Investigator {investigator_id}...")
    
    # 1. Format the anomaly details into a search query
    fraud_summary = json.dumps(anomaly_details)
    search_query = f"Data fabrication, round number preference, temporal data entry bursts, biological plausibility violations. Context: {fraud_summary}"
    
    # 2. Retrieve the top 3 most relevant regulatory clauses
    query_embedding = embedding_fn.embed_query(search_query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3
    )
    
    retrieved_clauses = "\n\n".join(results["documents"][0])
    sources = list(set([meta["source"] for meta in results["metadatas"][0]]))
    
    # 3. Prompt the Groq LLM to act as a Legal Auditor
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        return {"error": "GROQ_API_KEY not found."}
        
    llm = ChatGroq(temperature=0.1, model_name="llama-3.1-8b-instant", groq_api_key=groq_api_key)
    
    prompt_template = PromptTemplate.from_template(
        """You are a Clinical Trial Regulatory Affairs Expert.
Review the following investigator anomaly profile and the retrieved regulatory clauses. 
Determine exactly which clauses were violated and provide a short, strict compliance verdict.

ANOMALY PROFILE FOR INVESTIGATOR {investigator_id}:
{anomaly_profile}

RETRIEVED REGULATORY CLAUSES:
{regulatory_clauses}

Provide a strict, professional legal assessment (max 3 sentences) specifying the violations.
"""
    )
    
    chain = prompt_template | llm
    
    try:
        verdict = chain.invoke({
            "investigator_id": investigator_id,
            "anomaly_profile": fraud_summary,
            "regulatory_clauses": retrieved_clauses
        })
        
        return {
            "status": "success",
            "regulatory_verdict": verdict.content,
            "referenced_documents": sources
        }
    except Exception as e:
        logger.warning(f"RegRAG generation failed: {e}")
        return {"error": str(e)}