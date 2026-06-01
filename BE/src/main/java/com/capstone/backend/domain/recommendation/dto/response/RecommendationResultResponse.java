package com.capstone.backend.domain.recommendation.dto.response;

import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Getter
@Builder
public class RecommendationResultResponse {

    private UUID jobId;
    private BaseProductInfo baseProduct;
    private Integer matchScore;
    private String matchLabel;
    private String aiReason;
    private List<MainRecommendation> mainRecommendations;
    private List<SimilarProduct> similarUserProducts;
    private List<AlternativeProduct> alternativeProducts;
    private LocalDateTime createdAt;

    @Getter
    @Builder
    public static class BaseProductInfo {
        private UUID id;
        private String name;
        private String brand;
        private String imageUrl;
    }

    @Getter
    @Builder
    public static class MainRecommendation {
        private UUID id;
        private String name;
        private String brand;
        private String imageUrl;
        private Integer price;
        private Integer totalScore;
        private ScoreBreakdown breakdown;
    }

    @Getter
    @Builder
    public static class ScoreBreakdown {
        private Integer budgetFit;
        private Integer priceValue;
        private Integer reviewScore;
        private Integer personalization;
    }

    @Getter
    @Builder
    public static class SimilarProduct {
        private UUID id;
        private String name;
        private String brand;
        private String imageUrl;
        private Integer price;
        private Integer satisfactionPercent;
    }

    @Getter
    @Builder
    public static class AlternativeProduct {
        private UUID id;
        private String name;
        private String brand;
        private String imageUrl;
        private Integer price;
        private Double ingredientSimilarity;
    }
}
