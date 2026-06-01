package com.capstone.backend.domain.product.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
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
}
