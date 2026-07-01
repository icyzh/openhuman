import { create } from "zustand";
import { persist } from "zustand/middleware";
import { authLogin, authRegisterRoute, authMe } from "@repo/api-client";
import { ApiError } from "@repo/api-client";
import type { UserResponse } from "@repo/api-client";

const COOKIE_ATTRS = "path=/; SameSite=Lax";

function setOhToken(token: string | null) {
  if (typeof window === "undefined") return;

  if (token) {
    localStorage.setItem("oh_token", token);
    // Session cookie — cleared when browser closes, no TTL mismatch with JWT
    document.cookie = `oh_token=${token}; ${COOKIE_ATTRS}`;
  } else {
    localStorage.removeItem("oh_token");
    document.cookie = `oh_token=; ${COOKIE_ATTRS}; max-age=0`;
  }
}

export interface AuthState {
  token: string | null;
  user: UserResponse | null;
  isLoading: boolean;
  error: string | null;

  setToken: (token: string | null) => void;
  setUser: (user: UserResponse | null) => void;
  initialize: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    name: string,
  ) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoading: true,
      error: null,

      setToken: (token) => {
        setOhToken(token);
        set({ token, error: null });
      },

      setUser: (user) => set({ user }),

      initialize: async () => {
        const { token } = get();
        if (!token) {
          set({ isLoading: false });
          return;
        }

        try {
          const user = await authMe();
          set({ user, isLoading: false, error: null });
        } catch {
          setOhToken(null);
          set({ token: null, user: null, isLoading: false });
        }
      },

      login: async (email, password) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authLogin({ email, password });
          setOhToken(response.access_token);
          set({ token: response.access_token });
          // Best-effort fetch user; failure doesn't undo login
          try {
            const user = await authMe();
            set({ user, isLoading: false });
          } catch {
            set({ isLoading: false });
          }
        } catch (err) {
          setOhToken(null);
          set({
            token: null,
            user: null,
            isLoading: false,
            error: err instanceof Error ? err.message : "Login failed",
          });
          throw err;
        }
      },

      register: async (email, password, name) => {
        set({ isLoading: true, error: null });
        try {
          const response = await authRegisterRoute({ email, password, name });
          setOhToken(response.access_token);
          set({ token: response.access_token });
          try {
            const user = await authMe();
            set({ user, isLoading: false });
          } catch {
            set({ isLoading: false });
          }
        } catch (err) {
          setOhToken(null);
          set({
            token: null,
            user: null,
            isLoading: false,
            error: err instanceof Error ? err.message : "Registration failed",
          });
          throw err;
        }
      },

      logout: () => {
        setOhToken(null);
        set({ token: null, user: null, isLoading: false, error: null });
      },
    }),
    {
      name: "oh-auth",
      partialize: (state) => ({ token: state.token }),
    },
  ),
);
