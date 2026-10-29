import { webcrypto } from "node:crypto";
import { afterEach, describe, expect, it } from "vitest";
import { sha256File } from "./hash";

const originalCrypto = Object.getOwnPropertyDescriptor(window, "crypto");
const fakeFile = (text) => ({
  arrayBuffer: async () => {
    const bytes = new TextEncoder().encode(text);
    return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
  },
});

afterEach(() => {
  if (originalCrypto) Object.defineProperty(window, "crypto", originalCrypto);
  else delete window.crypto;
});

describe("sha256File", () => {
  it("returns the 64-character lowercase hex digest the API expects", async () => {
    Object.defineProperty(window, "crypto", { value: webcrypto, configurable: true });
    const digest = await sha256File(fakeFile("abc"));
    expect(digest).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    expect(digest).toMatch(/^[0-9a-f]{64}$/);
  });

  it("hashes empty files", async () => {
    Object.defineProperty(window, "crypto", { value: webcrypto, configurable: true });
    expect(await sha256File(fakeFile(""))).toBe("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  });

  it("explains when Web Crypto is unavailable (insecure context)", async () => {
    Object.defineProperty(window, "crypto", { value: {}, configurable: true });
    await expect(sha256File(fakeFile("abc"))).rejects.toThrow(/secure context/);
  });
});
