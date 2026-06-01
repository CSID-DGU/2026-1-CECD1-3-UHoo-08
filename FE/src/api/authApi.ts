import { api } from "../lib/api";

export interface TokenResponse {
  accessToken: string;
  refreshToken: string;
  isNewUser: boolean;
  user: {
    id: string;
    name: string;
    email: string | null;
  };
}

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export const socialLogin = (code: string) =>
  api.post<ApiResponse<TokenResponse>>("/auth/social", { code });
