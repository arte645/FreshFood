from supabase import create_client, Client
import os
from dotenv import load_dotenv
load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
response = (
            supabase.table("users")
            .select("*")
            .eq("login", "jdoe")
            .execute()
        )
print(response.data)