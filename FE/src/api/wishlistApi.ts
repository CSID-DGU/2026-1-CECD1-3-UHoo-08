import { api } from "../lib/api";

interface ApiResponse<T> {
  success: boolean;
  data: T;
}

export interface WishlistProduct {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  currentPrice: number | null;
  lowestPrice: number | null;
  category: string;
}

export interface WishlistItem {
  wishlistId: string;
  product: WishlistProduct;
  matchScore: number | null;
  createdAt: string;
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
