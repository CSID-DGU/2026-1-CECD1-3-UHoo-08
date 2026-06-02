package com.capstone.backend.domain.product.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@Getter
@Builder
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ProductDetailResponse {
    private UUID productId;
    private String name;
    private String brand;
    private String category;
    private String imageUrl;
    private Integer originalPrice;
    private Integer lowestPrice;
    private Object featureJson;
    private String reviewSummary;
    private BigDecimal averageScore;
    private Integer reviewCount;
    private List<StoreInfo> stores;
    private boolean wishlisted;
    private UUID wishlistId;

    @Getter
    @Builder
    @NoArgsConstructor
    @AllArgsConstructor
    public static class StoreInfo {
        private String storeName;
        private Integer price;
        private Boolean isLowest;
    }
}
