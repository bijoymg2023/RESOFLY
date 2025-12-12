# Hosting Guide: RESOFLY

This guide explains how to access RESOFLY from the internet or your local network.

## Option 1: On the Raspberry Pi (Preferred for Real data)

Since ResoFly connects to real hardware (Thermal Camera/GPS), it works best when hosted directly on the Pi.

### A. Local Network Access
If you are at home/office with the Pi:
1. Find the Pi's IP address: `hostname -I` (e.g., `192.168.1.15`).
2. Open your browser on any device (phone/laptop) and go to: `http://192.168.1.15:8000`.

### B. Remote Access (Tunneling)
To access the Pi when you are *away* from home (without opening unsafe firewall ports):
**Use Cloudflare Tunnel (Recommended)** or **Ngrok**.

**Example using Ngrok:**
1. Sign up at [ngrok.com](https://ngrok.com).
2. Install on Pi: `sudo snap install ngrok`.
3. Run: `ngrok http 8000`.
4. It will give you a public URL (e.g., `https://random-name.ngrok-free.app`). You can share this URL with anyone!

---

## Option 2: Cloud Hosting (Demo Mode)

If you want to host the app on a cloud server (like AWS, Render, Railway) just to demonstrate the UI (using **Mock Data**):

### Prerequisites
- Steps: `Dockerfile` is already included in the repo.

### Deploy to Render.com (Free Tier)
1. Fork/Push this repo to your GitHub.
2. Sign up at [dashboard.render.com](https://dashboard.render.com).
3. Click **New +** -> **Web Service**.
4. Connect your GitHub repo.
5. Settings:
   - **Runtime**: Docker
   - **Plan**: Free
6. Click **Create Web Service**.

**Note**: In the Cloud, there is no physical camera attached. The app will automatically run in "Mock Mode" (simulated video).
