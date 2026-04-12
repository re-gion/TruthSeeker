"""Supabase Storage and DB Client for FastAPI"""
from supabase import create_client, Client
from app.config import settings

def get_supabase() -> Client:
    """Initialize and return a Supabase client"""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY)

# Singleton instance
supabase: Client = get_supabase()
