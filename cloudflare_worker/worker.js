function bytesFromBase64(value) {
  const binary = atob(value);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

function pemToBytes(pem) {
  return bytesFromBase64(pem.replace(/-----[^-]+-----/g, "").replace(/\s+/g, ""));
}

function derToRaw(signature, size = 32) {
  const der = new Uint8Array(signature);
  if (der.length === size * 2) return der;
  let offset = 2;
  if (der[1] & 0x80) offset = 2 + (der[1] & 0x7f);
  if (der[offset++] !== 0x02) throw new Error("Bad ECDSA signature");
  const rLen = der[offset++]; let r = der.slice(offset, offset + rLen); offset += rLen;
  if (der[offset++] !== 0x02) throw new Error("Bad ECDSA signature");
  const sLen = der[offset++]; let s = der.slice(offset, offset + sLen);
  while (r.length > size && r[0] === 0) r = r.slice(1);
  while (s.length > size && s[0] === 0) s = s.slice(1);
  const raw = new Uint8Array(size * 2);
  raw.set(r, size - r.length); raw.set(s, size * 2 - s.length);
  return raw;
}

async function sha256Hex(text) {
  const hash = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function appToken(env) {
  const basic = btoa(`${env.EBAY_CLIENT_ID}:${env.EBAY_CLIENT_SECRET}`);
  const r = await fetch("https://api.ebay.com/identity/v1/oauth2/token", {
    method: "POST", headers: { Authorization: `Basic ${basic}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope",
  });
  if (!r.ok) throw new Error(`eBay OAuth ${r.status}`);
  return (await r.json()).access_token;
}

async function verifyNotification(rawBody, header, env) {
  const envelope = JSON.parse(new TextDecoder().decode(bytesFromBase64(header)));
  if (!envelope.kid || !envelope.signature) return false;
  const token = await appToken(env);
  const r = await fetch(`https://api.ebay.com/commerce/notification/v1/public_key/${encodeURIComponent(envelope.kid)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`eBay public key ${r.status}`);
  const keyBody = await r.json();
  const pem = keyBody.key || keyBody.publicKey;
  const key = await crypto.subtle.importKey("spki", pemToBytes(pem), { name: "ECDSA", namedCurve: "P-256" }, false, ["verify"]);
  return crypto.subtle.verify({ name: "ECDSA", hash: "SHA-1" }, key, derToRaw(bytesFromBase64(envelope.signature)), rawBody);
}

export default {
  async fetch(request, env) {
    if (!env.EBAY_ENDPOINT_URL || !env.EBAY_VERIFICATION_TOKEN) return new Response("Worker variables are missing", { status: 500 });
    const url = new URL(request.url);
    if (request.method === "GET" && url.searchParams.has("challenge_code")) {
      const challengeResponse = await sha256Hex(url.searchParams.get("challenge_code") + env.EBAY_VERIFICATION_TOKEN + env.EBAY_ENDPOINT_URL);
      return Response.json({ challengeResponse });
    }
    if (request.method === "POST") {
      const signature = request.headers.get("x-ebay-signature");
      if (!signature) return new Response("Missing signature", { status: 412 });
      const raw = await request.arrayBuffer();
      try {
        if (!(await verifyNotification(raw, signature, env))) return new Response("Invalid signature", { status: 412 });
        // DealBot does not retain eBay usernames or other buyer personal data.
        return new Response(null, { status: 204 });
      } catch (error) {
        console.error(error); return new Response("Verification error", { status: 500 });
      }
    }
    return new Response("Method not allowed", { status: 405 });
  },
};
