/** SHA-256 of a File as lowercase hex (the API expects a 64-character checksum). */
export async function sha256File(file) {
  if (!window.crypto?.subtle) throw new Error("Checksums need a secure context (https or localhost).");
  const digest = await window.crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
