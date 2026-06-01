package com.capstone.backend.domain.recommendation.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.recommendation.dto.request.RecommendationRequest;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationJobResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationResultResponse;
import com.capstone.backend.domain.recommendation.dto.response.RecommendationStatusResponse;
import com.capstone.backend.domain.recommendation.entity.Recommendation;
import com.capstone.backend.domain.recommendation.repository.RecommendationRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.entity.UserSkinProfile;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.capstone.backend.domain.user.repository.UserSkinProfileRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class RecommendationServiceImpl implements RecommendationService {

    private final RecommendationRepository recommendationRepository;
    private final ProductRepository productRepository;
    private final UserRepository userRepository;
    private final UserSkinProfileRepository skinProfileRepository;
    private final AgentClient agentClient;
    private final ObjectMapper objectMapper;

    @Override
    @Transactional
    public RecommendationJobResponse requestRecommendation(UUID userId, RecommendationRequest request) {
        Product product = productRepository.findById(request.getBaseProductId())
                .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        UserSkinProfile skinProfile = skinProfileRepository.findByUserId(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.SKIN_PROFILE_NOT_FOUND));

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        int tolerancePercent = request.getPriceTolerancePercent() != null
                ? request.getPriceTolerancePercent() : 10;

        LocalDateTime now = LocalDateTime.now();
        Recommendation job = Recommendation.builder()
                .user(user)
                .product(product)
                .searchPurpose(request.getSearchPurpose())
                .priceTolerancePercent(tolerancePercent)
                .status("PENDING")
                .progress(0)
                .createdAt(now)
                .updatedAt(now)
                .build();

        Recommendation saved = recommendationRepository.save(job);

        // Fire-and-forget: FastAPI 비동기 호출
        Map<String, Object> agentPayload = new HashMap<>();
        agentPayload.put("jobId", saved.getId().toString());
        agentPayload.put("baseProductId", request.getBaseProductId().toString());
        agentPayload.put("userId", userId.toString());
        agentPayload.put("searchPurpose", request.getSearchPurpose());
        agentPayload.put("priceTolerancePercent", tolerancePercent);

        Map<String, Object> userProfile = new HashMap<>();
        userProfile.put("skinType", skinProfile.getSkinType());
        userProfile.put("skinConcerns", skinProfile.getSkinConcerns() != null
                ? Arrays.asList(skinProfile.getSkinConcerns()) : List.of());
        userProfile.put("personalColor", skinProfile.getPersonalColor());
        agentPayload.put("userProfile", userProfile);

        agentClient.runAgent(agentPayload);

        return RecommendationJobResponse.of(saved.getId());
    }

    @Override
    @Transactional(readOnly = true)
    public RecommendationStatusResponse getStatus(UUID userId, UUID jobId) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        return RecommendationStatusResponse.from(job);
    }

    @Override
    @Transactional(readOnly = true)
    public RecommendationResultResponse getResult(UUID userId, UUID jobId) {
        Recommendation job = recommendationRepository.findByIdAndUserId(jobId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        if (!"COMPLETED".equals(job.getStatus())) {
            throw new BusinessException(ErrorCode.JOB_NOT_COMPLETED);
        }

        Product baseProduct = job.getProduct();

        Map<String, Object> resultMap = parseResult(job.getResult());

        Integer matchScore = toInt(resultMap.get("matchScore"));
        String matchLabel = (String) resultMap.get("matchLabel");
        String aiReason = (String) resultMap.get("aiReason");

        List<RecommendationResultResponse.MainRecommendation> mainRecommendations =
                parseMainRecommendations(resultMap.get("mainRecommendations"));

        List<RecommendationResultResponse.SimilarProduct> similarProducts = parseProducts(
                resultMap.get("similarUserProducts"), "satisfactionPercent");

        List<RecommendationResultResponse.AlternativeProduct> alternativeProducts =
                parseAlternativeProducts(resultMap.get("alternativeProducts"));

        return RecommendationResultResponse.builder()
                .jobId(job.getId())
                .baseProduct(RecommendationResultResponse.BaseProductInfo.builder()
                        .id(baseProduct.getId())
                        .name(baseProduct.getName())
                        .brand(baseProduct.getBrand())
                        .imageUrl(baseProduct.getImageUrl())
                        .build())
                .matchScore(matchScore)
                .matchLabel(matchLabel)
                .aiReason(aiReason)
                .mainRecommendations(mainRecommendations)
                .similarUserProducts(similarProducts)
                .alternativeProducts(alternativeProducts)
                .createdAt(job.getCreatedAt())
                .build();
    }

    private Map<String, Object> parseResult(String resultJson) {
        if (resultJson == null) return Map.of();
        try {
            return objectMapper.readValue(resultJson, new TypeReference<Map<String, Object>>() {});
        } catch (Exception e) {
            log.warn("Failed to parse recommendation result JSON: {}", e.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.MainRecommendation> parseMainRecommendations(Object raw) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> {
                    Map<String, Object> bd = (Map<String, Object>) m.get("breakdown");
                    RecommendationResultResponse.ScoreBreakdown breakdown = null;
                    if (bd != null) {
                        breakdown = RecommendationResultResponse.ScoreBreakdown.builder()
                                .budgetFit(toInt(bd.get("budgetFit")))
                                .priceValue(toInt(bd.get("priceValue")))
                                .reviewScore(toInt(bd.get("reviewScore")))
                                .personalization(toInt(bd.get("personalization")))
                                .build();
                    }
                    return RecommendationResultResponse.MainRecommendation.builder()
                            .id(parseUUID(m.get("productId")))
                            .name((String) m.get("name"))
                            .brand((String) m.get("brand"))
                            .imageUrl((String) m.get("imageUrl"))
                            .price(toInt(m.get("price")))
                            .totalScore(toInt(m.get("totalScore")))
                            .breakdown(breakdown)
                            .build();
                })
                .collect(Collectors.toList());
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.SimilarProduct> parseProducts(Object raw, String percentKey) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> RecommendationResultResponse.SimilarProduct.builder()
                        .id(parseUUID(m.get("id")))
                        .name((String) m.get("name"))
                        .brand((String) m.get("brand"))
                        .imageUrl((String) m.get("imageUrl"))
                        .price(toInt(m.get("price")))
                        .satisfactionPercent(toInt(m.get(percentKey)))
                        .build())
                .collect(Collectors.toList());
    }

    @SuppressWarnings("unchecked")
    private List<RecommendationResultResponse.AlternativeProduct> parseAlternativeProducts(Object raw) {
        if (!(raw instanceof List)) return List.of();
        return ((List<Map<String, Object>>) raw).stream()
                .map(m -> RecommendationResultResponse.AlternativeProduct.builder()
                        .id(parseUUID(m.get("id")))
                        .name((String) m.get("name"))
                        .brand((String) m.get("brand"))
                        .imageUrl((String) m.get("imageUrl"))
                        .price(toInt(m.get("price")))
                        .ingredientSimilarity(toDouble(m.get("ingredientSimilarity")))
                        .build())
                .collect(Collectors.toList());
    }

    private Integer toInt(Object o) {
        if (o == null) return null;
        if (o instanceof Number) return ((Number) o).intValue();
        return null;
    }

    private Double toDouble(Object o) {
        if (o == null) return null;
        if (o instanceof Number) return ((Number) o).doubleValue();
        return null;
    }

    private UUID parseUUID(Object o) {
        if (o == null) return null;
        try { return UUID.fromString(o.toString()); } catch (Exception e) { return null; }
    }
}
