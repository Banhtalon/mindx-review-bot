import { describe, expect, it } from "vitest";
import { createHmac, generateKeyPairSync } from "node:crypto";
import {
  createOrUpdateCheckRun,
  fetchAllIssueComments,
  fetchPullRequest,
  generateAppJwt,
  verifyWebhookSignature,
} from "../src/github.ts";

describe("GitHub Adapter & Crypto", () => {
  describe("Webhook Signature Verification", () => {
    const secret = "test-webhook-secret-12345";
    const payload = JSON.stringify({ action: "opened", pull_request: { number: 6 } });

    it("accepts valid HMAC-SHA256 signature", () => {
      const hmac = createHmac("sha256", secret);
      hmac.update(payload);
      const sigHeader = `sha256=${hmac.digest("hex")}`;

      expect(verifyWebhookSignature(payload, sigHeader, secret)).toBe(true);
    });

    it("rejects tampered payload with original signature", () => {
      const hmac = createHmac("sha256", secret);
      hmac.update(payload);
      const sigHeader = `sha256=${hmac.digest("hex")}`;

      expect(verifyWebhookSignature(payload + "tampered", sigHeader, secret)).toBe(false);
    });

    it("rejects wrong secret", () => {
      const hmac = createHmac("sha256", "wrong-secret");
      hmac.update(payload);
      const sigHeader = `sha256=${hmac.digest("hex")}`;

      expect(verifyWebhookSignature(payload, sigHeader, secret)).toBe(false);
    });

    it("rejects missing or malformed signature header", () => {
      expect(verifyWebhookSignature(payload, undefined, secret)).toBe(false);
      expect(verifyWebhookSignature(payload, "", secret)).toBe(false);
      expect(verifyWebhookSignature(payload, "invalid-header", secret)).toBe(false);
      expect(verifyWebhookSignature(payload, "sha1=12345", secret)).toBe(false);
    });
  });

  describe("App JWT Generation", () => {
    const { privateKey } = generateKeyPairSync("rsa", {
      modulusLength: 2048,
      publicKeyEncoding: { type: "spki", format: "pem" },
      privateKeyEncoding: { type: "pkcs8", format: "pem" },
    });

    it("generates a well-formed RS256 JWT", () => {
      const jwt = generateAppJwt("123456", privateKey);
      const parts = jwt.split(".");
      expect(parts).toHaveLength(3);

      const header = JSON.parse(Buffer.from(parts[0], "base64url").toString("utf-8"));
      expect(header.alg).toBe("RS256");
      expect(header.typ).toBe("JWT");

      const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8"));
      expect(payload.iss).toBe("123456");
      expect(typeof payload.iat).toBe("number");
      expect(typeof payload.exp).toBe("number");
      expect(payload.exp - payload.iat).toBe(660); // 11 mins total (exp now+600, iat now-60)
    });
  });

  describe("API Client Methods with Mocked Fetch", () => {
    it("fetches pull request and retrieves exact head SHA", async () => {
      const mockFetch = async () =>
        new Response(
          JSON.stringify({
            number: 6,
            head: { sha: "abc1234567890abcdef1234567890abcdef12345", ref: "test-branch" },
          }),
          { status: 200 }
        );

      const pr = await fetchPullRequest("Banhtalon/mindx-review-bot", 6, "mock-token", mockFetch as unknown as typeof fetch);
      expect(pr.number).toBe(6);
      expect(pr.head.sha).toBe("abc1234567890abcdef1234567890abcdef12345");
    });

    it("exhaustively paginates PR issue comments", async () => {
      let callCount = 0;
      const mockFetch = async (url: RequestInfo | URL) => {
        callCount++;
        const urlStr = String(url);
        const parsed = new URL(urlStr);
        const pageNum = parsed.searchParams.get("page");
        if (pageNum === "1") {
          const items = Array.from({ length: 100 }, (_, i) => ({ id: i + 1, body: `Comment ${i + 1}` }));
          return new Response(JSON.stringify(items), { status: 200 });
        } else if (pageNum === "2") {
          const items = Array.from({ length: 25 }, (_, i) => ({ id: i + 101, body: `Comment ${i + 101}` }));
          return new Response(JSON.stringify(items), { status: 200 });
        }
        return new Response(JSON.stringify([]), { status: 200 });
      };

      const comments = await fetchAllIssueComments(
        "Banhtalon/mindx-review-bot",
        6,
        "mock-token",
        mockFetch as unknown as typeof fetch
      );

      expect(callCount).toBe(2);
      expect(comments).toHaveLength(125);
      expect(comments[0].id).toBe(1);
      expect(comments[124].id).toBe(125);
    });

    it("creates check run enforcing check name 'terra-review-gate'", async () => {
      let capturedPayload: unknown;
      const mockFetch = async (_url: RequestInfo | URL, init?: RequestInit) => {
        capturedPayload = JSON.parse(String(init?.body));
        return new Response(JSON.stringify({ id: 98765, url: "https://api.github.com/..." }), { status: 201 });
      };

      const res = await createOrUpdateCheckRun(
        "Banhtalon/mindx-review-bot",
        {
          name: "terra-review-gate",
          head_sha: "abc1234567890abcdef1234567890abcdef12345",
          status: "completed",
          conclusion: "success",
          output: { title: "Terra Review Gate: Passed", summary: "All checks passed" },
        },
        "mock-token",
        undefined,
        mockFetch as unknown as typeof fetch
      );

      expect(res.id).toBe(98765);
      expect((capturedPayload as { name: string }).name).toBe("terra-review-gate");
    });

    it("throws error if check run name is not 'terra-review-gate'", async () => {
      await expect(
        createOrUpdateCheckRun(
          "Banhtalon/mindx-review-bot",
          {
            name: "other-check-name",
            head_sha: "abc1234567890abcdef1234567890abcdef12345",
            status: "completed",
            output: { title: "Title", summary: "Summary" },
          },
          "mock-token"
        )
      ).rejects.toThrow("Check run name must be exactly 'terra-review-gate'");
    });
  });
});
