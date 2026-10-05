const FERNET_VERSION = 0x80;
const FERNET_MINIMUM_TOKEN_LENGTH = 73;

function toArrayBuffer(value: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(value.byteLength);
  copy.set(value);
  return copy.buffer;
}

function decodeBase64Url(value: string): Uint8Array {
  if (!/^[A-Za-z0-9_-]+={0,2}$/.test(value)) {
    throw new Error("Invalid Fernet base64url data.");
  }
  const base64 = value.replace(/-/g, "+").replace(/_/g, "/").replace(/=+$/, "");
  const binary = atob(base64.padEnd(Math.ceil(base64.length / 4) * 4, "="));
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function encodeBase64Url(value: Uint8Array): string {
  let binary = "";
  for (const byte of value) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_");
}

function constantTimeEqual(left: Uint8Array, right: Uint8Array): boolean {
  if (left.length !== right.length) {
    return false;
  }
  let difference = 0;
  for (let index = 0; index < left.length; index += 1) {
    difference |= left[index] ^ right[index];
  }
  return difference === 0;
}

async function importHmacKey(key: Uint8Array): Promise<CryptoKey> {
  return await crypto.subtle.importKey(
    "raw",
    toArrayBuffer(key),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

export async function decryptFernet(
  token: string,
  encodedKey: string,
): Promise<string> {
  const key = decodeBase64Url(encodedKey);
  const tokenBytes = decodeBase64Url(token);
  if (key.length !== 32 || tokenBytes.length < FERNET_MINIMUM_TOKEN_LENGTH) {
    throw new Error("Invalid Fernet key or token.");
  }
  if (tokenBytes[0] !== FERNET_VERSION) {
    throw new Error("Unsupported Fernet token version.");
  }

  const signingKey = key.subarray(0, 16);
  const encryptionKey = key.subarray(16);
  const signedContent = tokenBytes.subarray(0, tokenBytes.length - 32);
  const suppliedSignature = tokenBytes.subarray(tokenBytes.length - 32);
  const expectedSignature = new Uint8Array(
    await crypto.subtle.sign(
      "HMAC",
      await importHmacKey(signingKey),
      toArrayBuffer(signedContent),
    ),
  );
  if (!constantTimeEqual(suppliedSignature, expectedSignature)) {
    throw new Error("Fernet token authentication failed.");
  }

  const aesKey = await crypto.subtle.importKey(
    "raw",
    toArrayBuffer(encryptionKey),
    "AES-CBC",
    false,
    ["decrypt"],
  );
  const plaintext = await crypto.subtle.decrypt(
    { name: "AES-CBC", iv: toArrayBuffer(tokenBytes.subarray(9, 25)) },
    aesKey,
    toArrayBuffer(tokenBytes.subarray(25, tokenBytes.length - 32)),
  );
  return new TextDecoder("utf-8", { fatal: true }).decode(plaintext);
}

export async function encryptFernet(
  plaintext: string,
  encodedKey: string,
): Promise<string> {
  const key = decodeBase64Url(encodedKey);
  if (key.length !== 32) {
    throw new Error("Invalid Fernet key.");
  }

  const signingKey = key.subarray(0, 16);
  const encryptionKey = key.subarray(16);
  const iv = crypto.getRandomValues(new Uint8Array(16));
  const timestamp = new Uint8Array(8);
  new DataView(timestamp.buffer).setBigUint64(
    0,
    BigInt(Math.floor(Date.now() / 1000)),
  );
  const header = new Uint8Array([FERNET_VERSION, ...timestamp, ...iv]);
  const aesKey = await crypto.subtle.importKey(
    "raw",
    toArrayBuffer(encryptionKey),
    "AES-CBC",
    false,
    ["encrypt"],
  );
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-CBC", iv },
      aesKey,
      new TextEncoder().encode(plaintext),
    ),
  );
  const signedContent = new Uint8Array([...header, ...ciphertext]);
  const signature = new Uint8Array(
    await crypto.subtle.sign(
      "HMAC",
      await importHmacKey(signingKey),
      signedContent,
    ),
  );
  return encodeBase64Url(new Uint8Array([...signedContent, ...signature]));
}
