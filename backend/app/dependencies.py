from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from supabase import create_client, Client
from app.config import settings
from app.db.supabase_client import get_supabase_client


security = HTTPBearer()


def _auth_error(error: str, detail: str) -> HTTPException:
    """Returns consistent error format for auth errors."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": error, "code": 401, "detail": detail},
    )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Validates Supabase JWT and extracts user_id and organization_id.
    Returns: {"user_id": str, "org_id": str}
    """
    token = credentials.credentials
    
    try:
        # Verify the JWT with Supabase
        supabase = get_supabase_client()
        
        # Get user from token
        user_response = supabase.auth.get_user(token)
        
        if user_response.user is None:
            raise _auth_error("INVALID_TOKEN", "Invalid or expired token")
        
        user_id = user_response.user.id
        
        # Fetch organization_id from profiles table
        profile_response = supabase.table("profiles").select("organization_id").eq("id", user_id).single().execute()
        
        if profile_response.data is None:
            raise _auth_error("PROFILE_NOT_FOUND", "User profile not found")
        
        org_id = profile_response.data["organization_id"]
        
        return {"user_id": user_id, "org_id": org_id}
    
    except JWTError:
        raise _auth_error("INVALID_TOKEN_FORMAT", "Invalid token format")
    except Exception as e:
        raise _auth_error("AUTH_FAILED", f"Authentication failed: {str(e)}")