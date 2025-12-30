import os
from dotenv import load_dotenv
from supabase import create_client, Client

def test_supabase_connection():
    # Load environment variables
    load_dotenv()
    
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print(f"--- Supabase Connection Test ---")
    print(f"URL: {url}")
    if key:
        print(f"Key detected: {key[:5]}...{key[-5:]} (Length: {len(key)})")
    else:
        print("Key detected: NONE")
    
    if not url or not key:
        print("\nERROR: SUPABASE_URL or SUPABASE_KEY missing from environment.")
        return

    try:
        print("\nAttempting to initialize client...")
        supabase: Client = create_client(url, key)
        print("Initialization SUCCESS.")
        
        print("\nAttempting to query 'tenants' table...")
        response = supabase.table("tenants").select("*").limit(1).execute()
        
        print(f"Query SUCCESS.")
        print(f"Data retrieved: {response.data}")
        
    except Exception as e:
        print(f"\nCaught Exception: {type(e).__name__}")
        print(f"Error Details: {e}")

if __name__ == "__main__":
    test_supabase_connection()
