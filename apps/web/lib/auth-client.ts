// Stub — Better Auth not yet configured.
// Replace with real client once auth is set up:
//   import { createAuthClient } from 'better-auth/client';
//   export const authClient = createAuthClient();

export const authClient = {
  getSession: async () => ({ data: null as { user?: unknown } | null }),
};
