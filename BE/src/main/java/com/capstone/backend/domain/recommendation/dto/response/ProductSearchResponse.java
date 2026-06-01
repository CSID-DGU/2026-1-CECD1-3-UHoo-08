package com.capstone.backend.domain.recommendation.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

@Getter
@NoArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ProductSearchResponse {

    private String query;
    private String category;
    private List<ProductSearchItem> products;

    @Getter
    @NoArgsConstructor
    @JsonInclude(JsonInclude.Include.NON_NULL)
    public static class ProductSearchItem {
        private UUID productId;
        private String name;
        private String brand;
        private String category;
        private String imageUrl;
        private Integer originalPrice;
        private Integer matchScore;
    }
}
