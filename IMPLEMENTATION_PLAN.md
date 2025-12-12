# Backend Implementation Plan - Thermo Vision Hub

## Hardware Context & Constraints
- **Device**: Raspberry Pi (Need generally efficient code).
- **Thermal Camera**: FLIR Lepton 3.5 (Radiometric data).
- **RGB Camera**: Raspberry Pi Camera Module.

## Phase 1-3: Hardware Features (COMPLETE)
- Alerts, Streaming, GPS, and System Status are implemented and verified.

## Phase 4: Production Readiness (Offline & Boot) (CURRENT)
To make the application "Deployment Ready" for the Raspberry Pi:

### 1. Refactor Frontend URLs
- **Problem**: Frontend currently fetches `http://127.0.0.1:8000/...`. This breaks if we access the Pi from another laptop (the browser will look for localhost on the laptop, not the Pi).
- **Solution**: Use relative paths (`/api/...`).
- **Dev Mode**: Configure Vite proxy to forward `/api` to localhost:8000.
- **Prod Mode**: Backend serves the frontend bundle directly.

### 2. Backward "Single-Process" Serving
- Modify `server.py` to mount the frontend `dist` `src`.
- Allows the whole app to run on a single port (8000) without needing Nginx.

### 3. Boot Configuration
- Create `thermo-vision.service` (Systemd unit file).
- Commands: `npm run build` (once), then start python server on boot.

## User Questions
- None. Proceeding with robust relative-path architecture.
