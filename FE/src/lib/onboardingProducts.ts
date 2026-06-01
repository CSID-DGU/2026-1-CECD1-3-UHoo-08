const KEY = "onboarding_products";

export interface OnboardingProduct {
  id: string;
  name: string;
  brand: string;
  imageUrl?: string | null;
}

export const getRegisteredProducts = (): OnboardingProduct[] => {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch {
    return [];
  }
};

export const addRegisteredProduct = (product: OnboardingProduct): OnboardingProduct[] => {
  const list = getRegisteredProducts();
  if (!list.find((p) => p.id === product.id)) {
    list.push(product);
    localStorage.setItem(KEY, JSON.stringify(list));
  }
  return list;
};

export const removeRegisteredProduct = (id: string): OnboardingProduct[] => {
  const list = getRegisteredProducts().filter((p) => p.id !== id);
  localStorage.setItem(KEY, JSON.stringify(list));
  return list;
};
