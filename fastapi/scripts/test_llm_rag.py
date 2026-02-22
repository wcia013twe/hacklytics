import asyncio
import os
import sys
import google.generativeai as genai
from sentence_transformers import SentenceTransformer

# Add parent to path to import backend modules if needed
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from cortex import AsyncCortexClient

async def test_llm_rag():
    print("="*60)
    print("Testing Actian VectorDB Output with Gemini LLM")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ Error: GEMINI_API_KEY environment variable not set.")
        print("You need an API key to test the LLM. Please provide one or set it in your environment.")
        return

    # 1. Setup DB
    actian_host = os.getenv("ACTIAN_HOST", "localhost")
    actian_port = int(os.getenv("ACTIAN_PORT", "50051"))
    print(f"Connecting to Actian VectorAI DB at {actian_host}:{actian_port}...")
    client = AsyncCortexClient(address=f"{actian_host}:{actian_port}")
    await client.connect()
    
    # 2. Embed Query
    query_text = "There is a toxic gas leak in a warehouse, workers are exposed."
    print(f"\nQuerying: '{query_text}'")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    vector = model.encode(query_text, normalize_embeddings=True).tolist()
    
    # 3. Retrieve context
    results = await client.search(
        collection_name="safety_protocols",
        query=vector,
        top_k=2,
        with_payload=True
    )
    
    if not results:
        print("❌ No protocols found.")
        await client.close()
        return
        
    print("\nRetrieved Context from Actian VectorDB:")
    context_texts = []
    for i, r in enumerate(results):
        src = r.payload.get('source', 'Unknown')
        text = r.payload.get('protocol_text', '')
        # Truncate text for display, but keep full for LLM
        print(f"  {i+1}. {src} (Score: {r.score:.4f})")
        context_texts.append(f"Source: {src}\n{text}")
        
    full_context = "\n---\n".join(context_texts)
    
    # 4. LLM Synthesis
    print("\nSending context to Gemini 2.5 Flash...")
    genai.configure(api_key=api_key)
    gemini_model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f"""
    You are an emergency response AI. You have been provided with safety protocols retrieved from 
    the ERG 2024 database corresponding to a reported incident.
    
    INCIDENT REPORT:
    {query_text}
    
    RETRIEVED ERG 2024 PROTOCOLS:
    {full_context}
    
    INSTRUCTIONS:
    Based ONLY on the provided ERG protocols, write a clear, concise (max 3-4 sentences), and 
    actionable recommendation for the first responders. Emphasize immediate life-saving actions 
    and required protective equipment based on the protocols.
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        print("\n" + "="*60)
        print("🧠 LLM SYNTHESIS RESULTS:")
        print("="*60)
        print(response.text)
        print("="*60)
    except Exception as e:
        print(f"\n❌ LLM Error: {e}")
        
    await client.close()

if __name__ == "__main__":
    asyncio.run(test_llm_rag())
