package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.ProductDto;
import com.capstone.backend.domain.product.dto.response.ProductDetailResponse;
import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.ProductFeature;
import com.capstone.backend.domain.product.entity.ProductInsight;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.repository.ProductFeatureRepository;
import com.capstone.backend.domain.product.repository.ProductInsightRepository;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import org.springframework.data.domain.PageRequest;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final ProductRepository productRepository;
    private final ProductFeatureRepository productFeatureRepository;
    private final ProductInsightRepository productInsightRepository;
    private final UserProductRepository userProductRepository;
    private final ObjectMapper objectMapper;

    @Override
    public ProductDto.Response getProduct(Long productId) {
        throw new BusinessException(ErrorCode.NOT_FOUND);
    }

    @Override
    @Transactional(readOnly = true)
    public ProductSearchResponse searchByKeyword(String keyword) {
        List<Product> products = productRepository
                .findByNameContainingIgnoreCaseOrBrandContainingIgnoreCaseOrderByNameAsc(
                        keyword, keyword, PageRequest.of(0, 20));
        List<ProductSearchResponse.ProductItem> items = products.stream()
                .map(p -> ProductSearchResponse.ProductItem.builder()
                        .id(p.getId())
                        .name(p.getName())
                        .brand(p.getBrand())
                        .category(p.getCategory())
                        .imageUrl(p.getImageUrl())
                        .originalPrice(p.getOriginalPrice())
                        .build())
                .toList();
        return new ProductSearchResponse(items);
    }

    @Override
    public List<ProductDto.Response> getProductsByCategory(String category) {
        throw new BusinessException(ErrorCode.NOT_FOUND);
    }

    @Override
    @Transactional
    public void recordView(UUID userId, UUID productId) {
        // 기존 VIEWED 기록 삭제 후 재삽입 (최신 시각으로 갱신, 중복 방지)
        userProductRepository.deleteByUserIdAndProductIdAndUsageType(userId, productId, "VIEWED");
        userProductRepository.save(UserProduct.builder()
                .userId(userId)
                .productId(productId)
                .usageType("VIEWED")
                .createdAt(LocalDateTime.now())
                .build());
    }

    @Override
    @Transactional(readOnly = true)
    public ProductSearchResponse getRecentlyViewed(UUID userId, int limit) {
        List<UUID> productIds = userProductRepository.findRecentViewedProductIds(
                userId, PageRequest.of(0, limit));
        if (productIds.isEmpty()) return new ProductSearchResponse(List.of());

        Map<UUID, Product> productMap = productRepository.findAllById(productIds)
                .stream()
                .collect(Collectors.toMap(Product::getId, Function.identity()));

        List<ProductSearchResponse.ProductItem> items = productIds.stream()
                .map(productMap::get)
                .filter(Objects::nonNull)
                .map(p -> ProductSearchResponse.ProductItem.builder()
                        .id(p.getId())
                        .name(p.getName())
                        .brand(p.getBrand())
                        .category(p.getCategory())
                        .imageUrl(p.getImageUrl())
                        .originalPrice(p.getOriginalPrice())
                        .build())
                .toList();
        return new ProductSearchResponse(items);
    }

    @Override
    @Transactional(readOnly = true)
    public ProductDetailResponse getProductDetail(UUID productId) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        ProductInsight insight = productInsightRepository.findByProduct_Id(productId).orElse(null);
        ProductFeature feature = productFeatureRepository.findByProduct_Id(productId).orElse(null);

        Object featureJson = null;
        if (feature != null && feature.getFeatureJson() != null) {
            try {
                featureJson = objectMapper.readValue(feature.getFeatureJson(), new TypeReference<Map<String, Object>>() {});
            } catch (Exception e) {
                log.warn("feature_json 파싱 실패 productId={}: {}", productId, e.getMessage());
                featureJson = feature.getFeatureJson();
            }
        }

        return ProductDetailResponse.builder()
                .productId(product.getId())
                .name(product.getName())
                .brand(product.getBrand())
                .category(product.getCategory())
                .imageUrl(product.getImageUrl())
                .originalPrice(insight != null ? insight.getOriginalPrice() : product.getOriginalPrice())
                .lowestPrice(insight != null ? insight.getLowestPrice() : null)
                .featureJson(featureJson)
                .reviewSummary(insight != null ? insight.getReviewSummary() : null)
                .averageScore(insight != null ? insight.getAverageScore() : null)
                .reviewCount(insight != null ? insight.getReviewCount() : null)
                .build();
    }
}
