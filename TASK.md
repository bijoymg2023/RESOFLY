# Backend Implementation - Thermo Vision Hub

- [x] **Phase 1: Alerts System** <!-- id: 0 -->
    - [x] Create `Alert` Pydantic model (`backend/server.py`) <!-- id: 1 -->
    - [x] Implement API endpoints (`GET /api/alerts`, `POST /api/alerts`, `PATCH /api/alerts/{id}/ack`) <!-- id: 2 -->
    - [x] Update frontend `AlertBox.tsx` to fetch data from API <!-- id: 3 -->
    - [x] Verify functionality <!-- id: 4 -->
- [x] **Phase 2: Video Stream** <!-- id: 5 -->
    - [x] Install dependencies (`numpy`, `opencv-python-headless`) <!-- id: 5.1 -->
    - [x] Create `camera.py` with `MockCamera` class <!-- id: 5.2 -->
    - [x] Create `GET /api/stream/thermal` endpoint in `server.py` <!-- id: 5.3 -->
    - [x] Update frontend `VideoStreamBox.tsx` to display stream <!-- id: 5.4 -->
    - [x] Verify stream works <!-- id: 5.5 -->
- [x] **Phase 3: GPS & Status** <!-- id: 7 -->
    - [x] Install `psutil` (for system status) <!-- id: 7.1 -->
    - [x] Create `SystemStatus` and `GPSData` models in `server.py` <!-- id: 7.2 -->
    - [x] Implement `GET /api/gps` and `GET /api/status` endpoints <!-- id: 7.3 -->
    - [x] Update `GPSCoordinateBox.tsx` to fetch API data <!-- id: 7.4 -->
    - [x] Update `ThermalDashboard.tsx` (System Status) to fetch API data <!-- id: 7.5 -->
- [x] **Phase 4: Production Readiness** <!-- id: 9 -->
    - [x] Refactor frontend to use relative API paths (`/api/...`) <!-- id: 9.1 -->
    - [x] Configure `vite.config.ts` proxy for dev mode <!-- id: 9.2 -->
    - [x] Update `server.py` to serve static files from `../dist` <!-- id: 9.3 -->
    - [x] Create `thermo-vision.service` systemd file <!-- id: 9.4 -->
    - [x] Verify production build (`npm run build` + `python server.py`) <!-- id: 9.5 -->
- [x] **Phase 5: Hosting Configuration** <!-- id: 10 -->
    - [x] Create `Dockerfile` <!-- id: 10.1 -->
    - [x] Create `HOSTING.md` guide <!-- id: 10.2 -->

# Future Work
- [ ] **Phase 6: Data Synchronization** (SQLite -> PostgreSQL)
- [x] **Phase 7: Authentication** (Login/JWT) <!-- id: 11 -->
    - [x] Install backend dependencies (`python-jose`, `passlib`) <!-- id: 11.1 -->
    - [x] Update `server.py` with User model and Auth logic <!-- id: 11.2 -->
    - [x] Protect API endpoints <!-- id: 11.3 -->
    - [x] Create `LoginPage.tsx` <!-- id: 11.4 -->
    - [x] Implement Auth Context in Frontend <!-- id: 11.5 -->
    - [x] Verify Login Flow <!-- id: 11.6 -->
