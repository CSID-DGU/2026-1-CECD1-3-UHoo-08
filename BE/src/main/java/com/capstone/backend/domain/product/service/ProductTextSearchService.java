package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.ProductInsight;
import com.capstone.backend.domain.product.repository.ProductInsightRepository;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductTextSearchService {

    private final ProductRepository productRepository;
    private final ProductInsightRepository productInsightRepository;
    private final WebClient webClient;
    private final ObjectMapper objectMapper;

    @Value("${naver.client-id}")
    private String naverClientId;

    @Value("${naver.client-secret}")
    private String naverClientSecret;

    @Value("${naver.shop-search-url}")
    private String naverShopSearchUrl;

    private static final long CACHE_HOURS = 6;

    @Transactional
    public ProductSearchResponse search(String q, int size) {
        if (q == null || q.isBlank()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }

        List<Product> dbResults = productRepository
                .findByNameContainingIgnoreCaseOrBrandContainingIgnoreCaseOrderByNameAsc(q, q, PageRequest.of(0, size));

        if (!dbResults.isEmpty()) {
            LocalDateTime threshold = LocalDateTime.now().minusHours(CACHE_HOURS);
            List<ProductSearchResponse.ProductItem> items = new ArrayList<>();

            for (Product p : dbResults) {
                ProductInsight insight = productInsightRepository.findByProduct_Id(p.getId()).orElse(null);

                // 캐시 만료 시 Naver API로 업데이트
                if (insight == null || insight.getLastUpdatedAt().isBefore(threshold)) {
                    try {
                        updateFromNaver(p, insight, q);
                        insight = productInsightRepository.findByProduct_Id(p.getId()).orElse(insight);
                    } catch (Exception e) {
                        log.warn("Naver API update failed for product {}: {}", p.getId(), e.getMessage());
                    }
                }

                items.add(toProductItem(p, insight));
            }
            return new ProductSearchResponse(items);
        }

        // DB에 없으면 Naver API에서 가져와서 저장
        return fetchAndSaveFromNaver(q, size);
    }

    private ProductSearchResponse fetchAndSaveFromNaver(String q, int size) {
        try {
            String responseBody = webClient.get()
                    .uri(naverShopSearchUrl + "?query={q}&display={size}", q, size)
                    .header("X-Naver-Client-Id", naverClientId)
                    .header("X-Naver-Client-Secret", naverClientSecret)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            JsonNode root = objectMapper.readTree(responseBody);
            JsonNode items = root.get("items");

            List<ProductSearchResponse.ProductItem> results = new ArrayList<>();
            if (items != null) {
                for (JsonNode item : items) {
                    ProductSearchResponse.ProductItem productItem = processNaverItem(item);
                    if (productItem != null) {
                        results.add(productItem);
                    }
                }
            }
            return new ProductSearchResponse(results);

        } catch (WebClientResponseException e) {
            log.error("Naver API error: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.EXTERNAL_API_ERROR);
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("Naver API unexpected error: {}", e.getMessage());
            throw new BusinessException(ErrorCode.EXTERNAL_API_ERROR);
        }
    }

    private ProductSearchResponse.ProductItem processNaverItem(JsonNode item) {
        try {
            String rawTitle = item.path("title").asText();
            final String name = rawTitle.replaceAll("<[^>]*>", "").trim();
            String brandRaw = item.path("brand").asText();
            if (brandRaw.isBlank()) brandRaw = item.path("maker").asText();
            if (brandRaw.isBlank()) brandRaw = item.path("mallName").asText("알 수 없음");
            final String brand = brandRaw;

            String imageUrl = item.path("image").asText(null);
            String link = item.path("link").asText(null);
            String category1 = item.path("category1").asText("");

            int lprice = 0;
            int hprice = 0;
            try { lprice = Integer.parseInt(item.path("lprice").asText("0")); } catch (NumberFormatException ignored) {}
            try { hprice = Integer.parseInt(item.path("hprice").asText("0")); } catch (NumberFormatException ignored) {}

            String category = mapCategory(category1, name);
            int originalPrice = hprice > 0 ? hprice : lprice;

            // DB에 저장
            Product product = productRepository.findByNameAndBrand(name, brand).orElseGet(() -> {
                Product newProduct = Product.builder()
                        .name(name).brand(brand).category(category)
                        .imageUrl(imageUrl).originalPrice(originalPrice)
                        .build();
                return productRepository.save(newProduct);
            });

            String mallName = item.path("mallName").asText("네이버쇼핑");
            String storesJson = buildStoresJson(mallName, lprice, link);

            ProductInsight insight = productInsightRepository.findByProduct_Id(product.getId()).orElseGet(() ->
                    ProductInsight.builder().product(product).build());

            ProductInsight updatedInsight = ProductInsight.builder()
                    .id(insight.getId())
                    .product(product)
                    .originalPrice(originalPrice)
                    .lowestPrice(lprice)
                    .stores(storesJson)
                    .reviewSummary(insight.getReviewSummary())
                    .averageScore(insight.getAverageScore())
                    .reviewCount(insight.getReviewCount())
                    .skinTypeSatisfaction(insight.getSkinTypeSatisfaction())
                    .savings(insight.getSavings())
                    .lastUpdatedAt(LocalDateTime.now())
                    .build();
            productInsightRepository.save(updatedInsight);

            return toProductItem(product, updatedInsight);

        } catch (Exception e) {
            log.warn("Failed to process Naver item: {}", e.getMessage());
            return null;
        }
    }

    private void updateFromNaver(Product product, ProductInsight insight, String q) {
        try {
            String responseBody = webClient.get()
                    .uri(naverShopSearchUrl + "?query={q}&display=1", product.getName() + " " + product.getBrand())
                    .header("X-Naver-Client-Id", naverClientId)
                    .header("X-Naver-Client-Secret", naverClientSecret)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            JsonNode root = objectMapper.readTree(responseBody);
            JsonNode items = root.path("items");
            if (items.isEmpty()) return;

            JsonNode item = items.get(0);
            int lprice = Integer.parseInt(item.path("lprice").asText("0"));
            String mallName = item.path("mallName").asText("네이버쇼핑");
            String link = item.path("link").asText(null);
            String storesJson = buildStoresJson(mallName, lprice, link);

            ProductInsight toSave = ProductInsight.builder()
                    .id(insight != null ? insight.getId() : null)
                    .product(product)
                    .originalPrice(product.getOriginalPrice())
                    .lowestPrice(lprice)
                    .stores(storesJson)
                    .lastUpdatedAt(LocalDateTime.now())
                    .build();
            productInsightRepository.save(toSave);
        } catch (Exception e) {
            log.warn("Failed to update product {} from Naver: {}", product.getId(), e.getMessage());
        }
    }

    private String buildStoresJson(String storeName, int price, String purchaseUrl) {
        return String.format("[{\"storeName\":\"%s\",\"price\":%d,\"isLowest\":true,\"purchaseUrl\":\"%s\"}]",
                storeName, price, purchaseUrl != null ? purchaseUrl : "");
    }

    private String mapCategory(String category1, String name) {
        String combined = (category1 + " " + name).toLowerCase();
        if (combined.contains("파운데이션") || combined.contains("쿠션") || combined.contains("비비") || combined.contains("컨실러")) return "base";
        if (combined.contains("선크림") || combined.contains("선스크린") || combined.contains("자외선")) return "sun";
        if (combined.contains("립") || combined.contains("틴트") || combined.contains("립스틱")) return "lip";
        return "skincare";
    }

    private ProductSearchResponse.ProductItem toProductItem(Product p, ProductInsight insight) {
        return ProductSearchResponse.ProductItem.builder()
                .id(p.getId())
                .name(p.getName())
                .brand(p.getBrand())
                .category(p.getCategory())
                .imageUrl(p.getImageUrl())
                .originalPrice(p.getOriginalPrice())
                .currentLowestPrice(insight != null ? insight.getLowestPrice() : null)
                .build();
    }
}
