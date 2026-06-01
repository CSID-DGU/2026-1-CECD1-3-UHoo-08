import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface WishlistItem {
  wishlistId: string;
  productId: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  price: number | null;
  matchScore: number | null;
}

export interface WishlistListData {
  wishlists: WishlistItem[];
  total: number;
}

export const getWishlists = () =>
  api.get<ApiResponse<WishlistListData>>("/wishlists");

export const addWishlist = (productId: string) =>
  api.post<ApiResponse<{ wishlistId: string }>>("/wishlists", { productId });

export const deleteWishlist = (wishlistId: string) =>
  api.delete<ApiResponse<unknown>>(`/wishlists/${wishlistId}`);
