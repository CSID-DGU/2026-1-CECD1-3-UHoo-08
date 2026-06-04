package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.ProductDto;
import com.capstone.backend.domain.product.dto.response.ProductDetailResponse;
import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.wishlist.entity.Wishlist;
import com.capstone.backend.domain.wishlist.repository.WishlistRepository;
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
import java.util.Optional;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ProductServiceImpl implements ProductService {

    private final ProductRepository productRepository;
    private final UserProductRepository userProductRepository;
    private final WishlistRepository wishlistRepository;
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
    public ProductDetailResponse getProductDetail(UUID userId, UUID productId) {
        Product product = productRepository.findById(productId)
                .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));

        Object featureJson = null;
        if (product.getFeatureJson() != null) {
            try {
                featureJson = objectMapper.readValue(product.getFeatureJson(),
                        new TypeReference<Map<String, Object>>() {});
            } catch (Exception e) {
                log.warn("feature_json 파싱 실패 productId={}: {}", productId, e.getMessage());
                featureJson = product.getFeatureJson();
            }
        }

        List<ProductDetailResponse.StoreInfo> stores = null;
        if (product.getStores() != null) {
            try {
                stores = objectMapper.readValue(product.getStores(),
                        new TypeReference<List<ProductDetailResponse.StoreInfo>>() {});
            } catch (Exception e) {
                log.warn("stores 파싱 실패 productId={}: {}", productId, e.getMessage());
            }
        }

        Optional<Wishlist> wishlist = wishlistRepository.findByUserIdAndProductId(userId, productId);

        return ProductDetailResponse.builder()
                .productId(product.getId())
                .name(product.getName())
                .brand(product.getBrand())
                .category(product.getCategory())
                .imageUrl(product.getImageUrl())
                .originalPrice(product.getOriginalPrice())
                .lowestPrice(product.getLowestPrice())
                .featureJson(featureJson)
                .reviewSummary(product.getReviewSummary())
                .averageScore(product.getAverageScore())
                .reviewCount(product.getReviewCount())
                .stores(stores)
                .wishlisted(wishlist.isPresent())
                .wishlistId(wishlist.map(Wishlist::getId).orElse(null))
                .build();
    }
}
