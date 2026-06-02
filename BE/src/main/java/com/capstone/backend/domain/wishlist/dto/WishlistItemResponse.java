package com.capstone.backend.domain.wishlist.dto;

import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.ProductInsight;
import com.capstone.backend.domain.wishlist.entity.Wishlist;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.UUID;

@Getter
@Builder
public class WishlistItemResponse {
    private UUID wishlistId;
    private ProductInfo product;
    private Integer matchScore;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class ProductInfo {
        private UUID id;
        private String name;
        private String brand;
        private String imageUrl;
        private Integer currentPrice;   // product.originalPrice (정가)
        private Integer lowestPrice;    // productInsight.lowestPrice (현재 최저가)
        private String category;
    }

    public static WishlistItemResponse of(Wishlist wishlist, ProductInsight insight) {
        Product p = wishlist.getProduct();
        return WishlistItemResponse.builder()
                .wishlistId(wishlist.getId())
                .product(ProductInfo.builder()
                        .id(p.getId())
                        .name(p.getName())
                        .brand(p.getBrand())
                        .imageUrl(p.getImageUrl())
                        .currentPrice(p.getOriginalPrice())
                        .lowestPrice(insight != null ? insight.getLowestPrice() : null)
                        .category(p.getCategory())
                        .build())
                .matchScore(wishlist.getMatchScore())
                .createdAt(wishlist.getCreatedAt())
                .build();
    }
}
