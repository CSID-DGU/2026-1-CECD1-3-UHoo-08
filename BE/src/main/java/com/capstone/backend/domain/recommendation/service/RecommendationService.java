package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.domain.recommendation.dto.request.RecommendationRequest;
import com.capstone.backend.domain.recommendation.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationJobResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;

import java.util.UUID;

public interface RecommendationService {
    RecommendationJobResponse requestRecommendation(UUID userId, RecommendationRequest request);
    RecommendationStatusResponse getStatus(UUID userId, UUID jobId);
    RecommendationResultResponse getResult(UUID userId, UUID jobId);
    ProductSearchResponse searchProducts(UUID userId, String query);
}
