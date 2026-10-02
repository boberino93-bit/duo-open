const encoder = new TextEncoder();

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function hex(buffer) {
  return [...new Uint8Array(buffer)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function cleanSegment(value, fallback) {
  const v = (value || fallback).replace(/[^A-Za-z0-9._-]/g, "-").slice(0, 100);
  return v || fallback;
}

async function emitGithubReceipt(env, receipt) {
  if (!env.GITHUB_REPOSITORY || !env.GITHUB_TOKEN) return;
  const url = `https://api.github.com/repos/${env.GITHUB_REPOSITORY}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "authorization": `Bearer ${env.GITHUB_TOKEN}`,
      "accept": "application/vnd.github+json",
      "content-type": "application/json",
      "user-agent": "duo-open-diagnostics-relay",
    },
    body: JSON.stringify({
      event_type: "duoopen-diagnostic-received",
      client_payload: receipt,
    }),
  });
  if (!response.ok) {
    console.log(`optional GitHub dispatch failed: ${response.status}`);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true });
    }
    if (request.method !== "POST" || url.pathname !== "/v1/diagnostics") {
      return json({ error: "not found" }, 404);
    }

    if (env.DUO_UPLOAD_KEY) {
      const expected = `Bearer ${env.DUO_UPLOAD_KEY}`;
      if (request.headers.get("authorization") !== expected) {
        return json({ received: false, error: "unauthorized" }, 401);
      }
    }

    const claimed = (request.headers.get("x-duo-sha256") || "").toLowerCase();
    if (!/^[a-f0-9]{64}$/.test(claimed)) {
      return json({ received: false, error: "invalid sha256" }, 400);
    }

    const contentLength = Number(request.headers.get("content-length") || 0);
    const maxBytes = Number(env.MAX_DIAGNOSTIC_BYTES || 12_000_000);
    if (contentLength <= 0 || contentLength > maxBytes) {
      return json({ received: false, error: "invalid diagnostic size" }, 413);
    }

    const bytes = await request.arrayBuffer();
    if (bytes.byteLength > maxBytes) {
      return json({ received: false, error: "diagnostic too large" }, 413);
    }

    const actual = hex(await crypto.subtle.digest("SHA-256", bytes));
    if (actual !== claimed) {
      return json({ received: false, error: "checksum mismatch" }, 409);
    }

    const version = cleanSegment(request.headers.get("x-duo-version"), "unknown");
    const now = new Date();
    const date = now.toISOString().slice(0, 10);
    const id = `DGN-${now.toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}-${crypto.randomUUID().slice(0, 8)}`;
    const repo = cleanSegment(env.ARTIFACTORY_REPO, "duoopen-diagnostics-local");
    const relativePath = `${version}/${date}/${id}-${actual.slice(0, 12)}.zip`;
    const base = (env.ARTIFACTORY_BASE_URL || "").replace(/\/$/, "");

    if (!base.startsWith("https://") || !env.ARTIFACTORY_TOKEN) {
      return json({ received: false, error: "relay storage is not configured" }, 503);
    }

    const artifactUrl = `${base}/artifactory/${repo}/${relativePath}`;
    const put = await fetch(artifactUrl, {
      method: "PUT",
      headers: {
        "authorization": `Bearer ${env.ARTIFACTORY_TOKEN}`,
        "content-type": "application/zip",
        "accept": "application/json",
        "x-checksum-sha256": actual,
      },
      body: bytes,
    });

    const putText = await put.text();
    if (put.status !== 201) {
      return json({
        received: false,
        error: "artifactory rejected diagnostic",
        storageStatus: put.status,
        storageBody: putText.slice(0, 300),
      }, 502);
    }

    // Strong receipt: ask Artifactory to find the exact SHA-256 inside the
    // configured repository. Success means the checksum was persisted/indexed.
    const verifyUrl = `${base}/artifactory/api/search/checksum?sha256=${actual}&repos=${encodeURIComponent(repo)}`;
    const verify = await fetch(verifyUrl, {
      headers: {
        "authorization": `Bearer ${env.ARTIFACTORY_TOKEN}`,
        "accept": "application/json",
        "X-Result-Detail": "info",
      },
    });
    const verifyText = await verify.text();
    if (!verify.ok || !verifyText.includes(relativePath)) {
      return json({
        received: false,
        error: "artifactory persistence could not be verified",
        storageStatus: verify.status,
      }, 502);
    }

    const receipt = {
      received: true,
      diagnosticId: id,
      sha256: actual,
      artifactPath: `${repo}/${relativePath}`,
      receivedAt: now.toISOString(),
    };

    await emitGithubReceipt(env, receipt);
    return json(receipt, 201);
  },
};
