# Secure eBay deletion-notification Worker

Replace the temporary Worker code with `worker.js`. In Cloudflare Worker **Settings → Variables and Secrets**, add:

- `EBAY_ENDPOINT_URL` as **Text**: the exact public Worker URL, including the final `/` if eBay has it.
- `EBAY_VERIFICATION_TOKEN` as **Secret**: the same private 40–80 character value entered at eBay.
- `EBAY_CLIENT_ID` as **Secret**: Production App ID.
- `EBAY_CLIENT_SECRET` as **Secret**: Production Cert ID.

Deploy the Worker, then save the same endpoint URL/token in eBay. This version validates eBay's signed POST notifications before returning HTTP 204; it does not blindly acknowledge arbitrary POST requests. Never paste any of these secrets into Discord, GitHub, or screenshots.
