import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, get, normalizeError, post, setUnauthorizedHandler, tokenStore } from "./client";

const httpError = (status, data, url = "/grades") =>
  Object.assign(new Error(`HTTP ${status}`), { isAxiosError: true, response: { status, data, headers: {} }, config: { url } });

describe("normalizeError", () => {
  it("reports an unreachable server", () => {
    expect(normalizeError({})).toMatchObject({ status: 0, code: "network" });
    expect(normalizeError({}).message).toMatch(/Cannot reach the server/);
  });

  it("uses the string detail from application errors", () => {
    expect(normalizeError({ response: { status: 409, data: { detail: "Duplicate appeal", code: "conflict" } } })).toEqual({
      status: 409,
      code: "conflict",
      message: "Duplicate appeal",
    });
  });

  it("flattens FastAPI validation lists, dropping the 'body' prefix", () => {
    const error = {
      response: {
        status: 422,
        data: { detail: [{ loc: ["body", "scores", 0, "score"], msg: "Input should be a valid number" }, { loc: ["body", "reason"], msg: "Field required" }] },
      },
    };
    expect(normalizeError(error).message).toBe("scores.0.score: Input should be a valid number; reason: Field required");
  });

  it("hides server internals behind a generic message", () => {
    expect(normalizeError({ response: { status: 500, data: "<html>trace</html>" } }).message).toBe("The server hit an unexpected error.");
    expect(normalizeError({ response: { status: 404, data: {} } })).toMatchObject({ code: "error", message: "Something went wrong." });
  });
});

describe("tokenStore", () => {
  it("stores, reads and clears the token", () => {
    expect(tokenStore.get()).toBeNull();
    tokenStore.set("abc");
    expect(tokenStore.get()).toBe("abc");
    tokenStore.clear();
    expect(tokenStore.get()).toBeNull();
  });
});

describe("axios instance", () => {
  const originalAdapter = api.defaults.adapter;
  let seen;

  beforeEach(() => {
    seen = [];
    setUnauthorizedHandler(null);
    api.defaults.adapter = originalAdapter;
  });

  const respondWith = (handler) => {
    api.defaults.adapter = async (config) => {
      seen.push(config);
      return handler(config);
    };
  };
  const ok = (data) => (config) => ({ data, status: 200, statusText: "OK", headers: {}, config });

  it("sends the Bearer token only when signed in", async () => {
    respondWith(ok({ fine: true }));
    await get("/courses");
    expect(seen[0].headers.Authorization).toBeUndefined();

    tokenStore.set("tok-123");
    await get("/courses");
    expect(seen[1].headers.Authorization).toBe("Bearer tok-123");
  });

  it("returns response data and forwards query params and bodies", async () => {
    respondWith(ok({ items: [] }));
    expect(await get("/submissions", { page: 2, status: "graded" })).toEqual({ items: [] });
    expect(seen[0].params).toEqual({ page: 2, status: "graded" });

    await post("/appeals", { grade_id: 4, reason: "x" });
    expect(JSON.parse(seen[1].data)).toEqual({ grade_id: 4, reason: "x" });
    expect(seen[1].method).toBe("post");
  });

  it("rejects with a normalized error", async () => {
    respondWith(() => Promise.reject(httpError(403, { detail: "Not authorized to grade", code: "forbidden" })));
    await expect(post("/grades", {})).rejects.toEqual({ status: 403, code: "forbidden", message: "Not authorized to grade" });
  });

  it("clears the token and notifies the app on an expired session", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    tokenStore.set("stale");
    respondWith(() => Promise.reject(httpError(401, { detail: "Token expired" })));

    await expect(get("/grades")).rejects.toMatchObject({ status: 401 });

    expect(tokenStore.get()).toBeNull();
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it("does not treat a wrong password as an expired session", async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);
    tokenStore.set("keep-me");
    respondWith(() => Promise.reject(httpError(401, { detail: "Invalid email or password" }, "/auth/login")));

    await expect(post("/auth/login", {})).rejects.toMatchObject({ status: 401 });

    expect(tokenStore.get()).toBe("keep-me");
    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
