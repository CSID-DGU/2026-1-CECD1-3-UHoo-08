package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.dto.ProductDto;
import com.capstone.backend.domain.product.dto.response.ProductDetailResponse;
import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;

import java.util.List;
import java.util.UUID;

public interface ProductService {
    ProductDto.Response getProduct(Long productId);
    ProductSearchResponse searchByKeyword(String keyword);
    List<ProductDto.Response> getProductsByCategory(String category);
    ProductDetailResponse getProductDetail(UUID productId);
    void recordView(UUID userId, UUID productId);
    ProductSearchResponse getRecentlyViewed(UUID userId, int limit);
}
