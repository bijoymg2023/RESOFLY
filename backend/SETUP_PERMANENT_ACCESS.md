# How to set up a Permanent Domain for RESOFLY

To get a permanent link (e.g., `https://resofly.yourname.com`) that never changes and auto-starts on boot, you need a **Cloudflare Account** and a **Domain Name** (like `google.com`, but yours).

**Prerequisites:**
1.  A free Cloudflare Account.
2.  A domain name added to that Cloudflare account.

## Step 1: Create the Tunnel in the Cloudflare Dashboard
*(Do this on your Mac/PC)*

1.  Go to the **[Cloudflare Zero Trust Dashboard](https://one.dash.cloudflare.com/)**.
2.  Navigate to **Networks** > **Tunnels**.
3.  Click **Create a Tunnel**.
4.  Select **Cloudflared** (connector).
5.  Name it `resofly-pi` and click **Save Tunnel**.

## Step 2: Install on Raspberry Pi
1.  On the "Install connector" page, you will see a box with commands.
2.  Click the **Debian** icon (the red swirl) or **64-bit**.
3.  **Copy the command** in the box. It looks like this:
    ```bash
    sudo cloudflared service install eyJhIjoiM...
    ```
4.  **Paste and Run** this command in your Raspberry Pi SSH terminal.
    *   This automatically installs the service and links it to your account.
    *   *Note: If you already ran my previous setup script, run `sudo systemctl stop resofly-tunnel` first.*

5.  Back in the Cloudflare Dashboard, you should see the status turn **Healthy** (green). Click **Next**.

## Step 3: Connect the Domain
1.  In the **Public Hostnames** tab.
2.  **Subdomain**: Enter `resofly` (or whatever you want).
3.  **Domain**: Select your domain from the dropdown.
4.  **Service**:
    *   Type: `HTTP`
    *   URL: `localhost:8000`
5.  Click **Save Tunnel**.

## Done!
You can now visit `https://resofly.yourdomain.com` anytime.
*   It automatically starts when the Pi turns on.
*   It never changes URL.
*   It is secure (HTTPS).
