import secrets
import time
from typing import Optional, Dict
from fastapi import FastAPI, Request, Response, HTTPException, status, Depends, Header
from fastapi.middleware.cors import CORSMiddleware # To allow frontend requests
from pydantic import BaseModel

# --- Configuration ---
SESSION_COOKIE_NAME = "my_app_session_id"
CSRF_COOKIE_NAME = "my_app_csrf_token"
SESSION_TTL_SECONDS = 3600  # 1 hour session lifetime
CSRF_TOKEN_HEADER = "X-CSRF-Token" # Custom header for CSRF token

# --- Simple In-Memory Stores (Replace with DB/Redis in production) ---
# Store active sessions: {session_id: {"username": username, "expires": timestamp}}
active_sessions: Dict[str, Dict] = {}
# Simulated user database
mock_users_db = {
    "user": "hashed_password_placeholder" # In real apps, store hashed passwords
}

# --- Pydantic Models ---
class UserCredentials(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    username: str
    csrf_token: str

# --- FastAPI App Initialization ---
app = FastAPI(title="Secure Login Backend")

# --- CORS Middleware ---
# Allows requests from your frontend (adjust origin if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["null", "http://localhost", "http://127.0.0.1"], # Add your frontend origin(s) here. "null" for file://
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", CSRF_TOKEN_HEADER], # Allow the custom CSRF header
)


# --- Helper Functions ---
def generate_session_id() -> str:
    return secrets.token_urlsafe(32)

def generate_csrf_token() -> str:
    return secrets.token_hex(32)

def create_session(username: str) -> str:
    """Creates a new session, stores it, and returns the session ID."""
    session_id = generate_session_id()
    expires = time.time() + SESSION_TTL_SECONDS
    active_sessions[session_id] = {"username": username, "expires": expires}
    print(f"Session created for {username}: {session_id[:8]}..., expires: {time.ctime(expires)}")
    return session_id

def get_session_data(session_id: str) -> Optional[Dict]:
    """Retrieves session data if valid and not expired."""
    session = active_sessions.get(session_id)
    if not session:
        print(f"Session not found: {session_id[:8]}...")
        return None
    if time.time() > session["expires"]:
        print(f"Session expired: {session_id[:8]}...")
        # Clean up expired session
        del active_sessions[session_id]
        return None
    # Extend session lifetime on activity (optional)
    session["expires"] = time.time() + SESSION_TTL_SECONDS
    print(f"Session validated for {session['username']}: {session_id[:8]}...")
    return session

def delete_session(session_id: str):
    """Deletes a session from the store."""
    if session_id in active_sessions:
        print(f"Deleting session: {session_id[:8]}...")
        del active_sessions[session_id]

# --- CSRF Protection Dependency ---
async def verify_csrf(
    request: Request,
    csrf_token_header: Optional[str] = Header(None, alias=CSRF_TOKEN_HEADER)
):
    """
    Dependency to verify CSRF token using Double Submit Cookie pattern.
    Compares token from header with token from cookie.
    """
    csrf_token_cookie = request.cookies.get(CSRF_COOKIE_NAME)

    if not csrf_token_cookie or not csrf_token_header:
        print("CSRF Error: Missing token in cookie or header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or mismatch",
        )

    if not secrets.compare_digest(csrf_token_cookie, csrf_token_header):
        print(f"CSRF Error: Token mismatch. Cookie: {csrf_token_cookie[:8]}... Header: {csrf_token_header[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or mismatch",
        )
    print("CSRF token verified successfully.")


# --- API Endpoints ---

@app.post("/login", response_model=UserInfo)
async def login(credentials: UserCredentials, response: Response):
    """
    Handles user login.
    - Validates credentials (mock validation).
    - Creates a session.
    - Sets HttpOnly session cookie.
    - Sets CSRF token cookie (readable by JS).
    - Returns user info and CSRF token in body.
    """
    print(f"Login attempt for user: {credentials.username}")
    # --- !!! IMPORTANT: Replace with secure password verification !!! ---
    stored_password_hash = mock_users_db.get(credentials.username)
    # Simulate password check (DO NOT use plain text comparison in production)
    is_valid_password = (stored_password_hash is not None and
                         credentials.password == "password123") # Replace with hash check

    if not is_valid_password:
        print("Login failed: Invalid credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}, # Standard header for 401
        )

    # --- Credentials Valid - Create Session ---
    session_id = create_session(credentials.username)
    csrf_token = generate_csrf_token()

    # Set Session Cookie (HttpOnly, Secure, SameSite)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,       # Cannot be accessed by JavaScript
        secure=True,         # Only sent over HTTPS (requires HTTPS setup)
        samesite="lax",      # Protects against CSRF to some extent
        max_age=SESSION_TTL_SECONDS,
        path="/",
    )

    # Set CSRF Token Cookie (NOT HttpOnly, so JS can read it)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,      # JS needs to read this
        secure=True,         # Only sent over HTTPS
        samesite="lax",
        max_age=SESSION_TTL_SECONDS, # Should ideally match session TTL
        path="/",
    )

    print(f"Login successful for {credentials.username}. Session: {session_id[:8]}..., CSRF: {csrf_token[:8]}...")
    return UserInfo(username=credentials.username, csrf_token=csrf_token)


@app.post("/logout")
async def logout(request: Request, response: Response, _=Depends(verify_csrf)):
    """
    Handles user logout.
    - Requires valid CSRF token (via Depends).
    - Deletes the session from the server store.
    - Clears the session cookie.
    - Clears the CSRF cookie.
    """
    print("Logout attempt...")
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        delete_session(session_id)

    # Clear cookies by setting expiry in the past
    response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/", secure=True, httponly=False, samesite="lax")

    print("Logout successful. Cookies cleared.")
    return {"message": "Logout successful"}


@app.get("/session", response_model=UserInfo)
async def check_session(request: Request, response: Response):
    """
    Checks if a valid session exists based on the session cookie.
    - If valid, returns user info and a *new* CSRF token.
    - Renews session and CSRF cookies.
    """
    print("Session check attempt...")
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        print("Session check failed: No session cookie found.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session_data = get_session_data(session_id)
    if not session_data:
        # Session invalid or expired, clear potentially stale cookies
        response.delete_cookie(SESSION_COOKIE_NAME, path="/", secure=True, httponly=True, samesite="lax")
        response.delete_cookie(CSRF_COOKIE_NAME, path="/", secure=True, httponly=False, samesite="lax")
        print("Session check failed: Invalid or expired session.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalid or expired")

    # --- Session Valid - Renew session and issue new CSRF ---
    username = session_data["username"]
    new_csrf_token = generate_csrf_token()

    # Renew Session Cookie (optional but good practice)
    response.set_cookie(
        key=SESSION_COOKIE_NAME, value=session_id,
        httponly=True, secure=True, samesite="lax", max_age=SESSION_TTL_SECONDS, path="/"
    )
    # Renew CSRF Token Cookie with new value
    response.set_cookie(
        key=CSRF_COOKIE_NAME, value=new_csrf_token,
        httponly=False, secure=True, samesite="lax", max_age=SESSION_TTL_SECONDS, path="/"
    )

    print(f"Session check successful for {username}. Renewed cookies. New CSRF: {new_csrf_token[:8]}...")
    return UserInfo(username=username, csrf_token=new_csrf_token)

# --- Root endpoint for basic check ---
@app.get("/")
async def root():
    return {"message": "Secure Login Backend is running!"}

# --- Optional: Run directly with uvicorn for local dev ---
# if __name__ == "__main__":
#     import uvicorn
#     print("Starting Uvicorn server for local development on http://127.0.0.1:8000")
#     # Note: For HTTPS locally, you'd need to configure uvicorn with --ssl-keyfile and --ssl-certfile
#     # Cookies marked 'Secure' won't work over HTTP. You might temporarily set secure=False during local HTTP dev.
#     uvicorn.run(app, host="127.0.0.1", port=8000)