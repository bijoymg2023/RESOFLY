# Authentication Implementation Plan

## Goal
Secure the ResoFly dashboard with a username/password login system to prevent unauthorized access when exposed to the internet/network.

## Architecture

### Backend (FastAPI)
- **Library**: `python-jose` (JWT), `passlib` (Hashing).
- **Model**: `UserDB` (username, hashed_password).
- **Endpoints**:
    - `POST /api/token` (Login) -> Returns JWT access token.
    - `GET /api/users/me` (Verify token).
- **Middleware/Dependency**: `get_current_user` dependency will be added to sensitive routes (`/stream`, `/alerts`, `/gps`).
- **Default User**: Create an efficient startup script to ensure a default `admin` user exists.

### Frontend (React)
- **Page**: `LoginPage.tsx` (New component).
- **State**: Store JWT in `localStorage`.
- **Logic**:
    - On App load, check for token.
    - If no token -> Redirect to `/login`.
    - If API returns 401 -> Redirect to `/login`.
    - `VideoStreamBox` needs to handle auth (Pass token in URL or use Cookies? MJPEG is tricky with Headers).
        - *Decision*: For MJPEG, we might use a Query Parameter `?token=...` or Cookies. Cookies are easier for `<img>` tags. Let's use **Cookies** for the stream authentication or specific query param.

## Proposed Changes

### Backend
#### [MODIFY] `backend/server.py`
- Add `UserDB` model.
- Add `Token` pydantic model.
- Add `authenticate_user`, `create_access_token` functions.
- Add `/token` endpoint.
- Protect `get_alerts`, `gen_frames`, etc.

### Frontend
#### [NEW] `src/pages/Login.tsx`
- Simple Login form.
#### [MODIFY] `src/App.tsx`
- Add `AuthProvider` wrapper.
- Add Route for `/login`.
- Protect `/` route.

## Verification
1. Try to access dashboard -> Should redirect to Login.
2. Enter wrong password -> Error message.
3. Enter correct password -> Dashboard loads.
4. Verify Stream loads (Auth check).
