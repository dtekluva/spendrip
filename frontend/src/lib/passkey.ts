/** Face ID / fingerprint via WebAuthn passkeys. The server sends options as JSON with base64url fields. */
const b64uToBuf = (s: string) => {
  const pad = '='.repeat((4 - (s.length % 4)) % 4);
  const bin = atob((s + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0)).buffer;
};
const bufToB64u = (b: ArrayBuffer) => btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

export const passkeysSupported = () => typeof window !== 'undefined' && !!window.PublicKeyCredential && !!navigator.credentials;

export async function createPasskey(options: any): Promise<any> {
  const publicKey: PublicKeyCredentialCreationOptions = {
    ...options,
    challenge: b64uToBuf(options.challenge),
    user: { ...options.user, id: b64uToBuf(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((c: any) => ({ ...c, id: b64uToBuf(c.id) })),
  };
  const cred = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential;
  const r = cred.response as AuthenticatorAttestationResponse;
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type,
    response: { clientDataJSON: bufToB64u(r.clientDataJSON), attestationObject: bufToB64u(r.attestationObject),
      transports: r.getTransports?.() ?? [] },
    clientExtensionResults: cred.getClientExtensionResults(), authenticatorAttachment: (cred as any).authenticatorAttachment ?? null,
  };
}

export async function getPasskey(options: any): Promise<any> {
  const publicKey: PublicKeyCredentialRequestOptions = {
    ...options,
    challenge: b64uToBuf(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((c: any) => ({ ...c, id: b64uToBuf(c.id) })),
  };
  const cred = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential;
  const r = cred.response as AuthenticatorAssertionResponse;
  return {
    id: cred.id, rawId: bufToB64u(cred.rawId), type: cred.type,
    response: { clientDataJSON: bufToB64u(r.clientDataJSON), authenticatorData: bufToB64u(r.authenticatorData),
      signature: bufToB64u(r.signature), userHandle: r.userHandle ? bufToB64u(r.userHandle) : null },
    clientExtensionResults: cred.getClientExtensionResults(), authenticatorAttachment: (cred as any).authenticatorAttachment ?? null,
  };
}
