package com.capstone.backend.domain.product.controller;

import com.capstone.backend.common.response.ApiResponse;
import com.capstone.backend.domain.product.dto.request.RecognizeRequest;
import com.capstone.backend.domain.product.dto.response.ProductDetailResponse;
import com.capstone.backend.domain.product.dto.response.ProductRecognizeResponse;
import com.capstone.backend.domain.product.dto.response.ProductSearchResponse;
import com.capstone.backend.domain.product.service.ProductRecognizeService;
import com.capstone.backend.domain.product.service.ProductService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.*;

import java.util.UUID;

@RestController
@RequiredArgsConstructor
@Tag(name = "7. Product", description = "상품 관련 API")
public class ProductController {

    private final ProductService productService;
    private final ProductRecognizeService productRecognizeService;

    @Operation(
            summary = "제품 인식 (IMAGE / NFC / TEXT)",
            description = "FastAPI input_agent → product_agent 순차 호출 (동기). " +
                    "type: IMAGE(base64), NFC(URL), TEXT(평문). 결과로 productId 포함 상품 정보 반환."
    )
    @PostMapping("/products/recognize")
    public ResponseEntity<ApiResponse<ProductRecognizeResponse>> recognize(
            @AuthenticationPrincipal UUID userId,
            @Valid @RequestBody RecognizeRequest request) {
        return ResponseEntity.ok(ApiResponse.success(productRecognizeService.recognize(userId, request)));
    }

    @Operation(
            summary = "제품 상세 조회",
            description = "product_features(feature_json) + product_insights 를 합산해 반환. " +
                    "recognize 이후 productId로 호출하거나, 추천 결과 상품 확인 시 사용."
    )
    @GetMapping("/products/{productId}")
    public ResponseEntity<ApiResponse<ProductDetailResponse>> getProductDetail(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID productId) {
        return ResponseEntity.ok(ApiResponse.success(productService.getProductDetail(productId)));
    }

    @Operation(
            summary = "제품 키워드 검색",
            description = "name/brand ILIKE 검색. 최대 20개 반환. 온보딩 제품 등록 등 간단한 검색에 사용."
    )
    @GetMapping("/products/search")
    public ResponseEntity<ApiResponse<ProductSearchResponse>> searchProducts(
            @RequestParam String keyword) {
        return ResponseEntity.ok(ApiResponse.success(productService.searchByKeyword(keyword)));
    }

    @Operation(
            summary = "상품 조회 기록",
            description = "user_products 테이블에 VIEWED 타입으로 기록. 홈 화면 '최근 본 상품' 데이터 소스."
    )
    @PostMapping("/products/{productId}/view")
    public ResponseEntity<ApiResponse<Void>> recordView(
            @AuthenticationPrincipal UUID userId,
            @PathVariable UUID productId) {
        productService.recordView(userId, productId);
        return ResponseEntity.ok(ApiResponse.success(null));
    }

    @Operation(
            summary = "최근 본 상품 조회",
            description = "VIEWED 타입 기준 최신순. 홈 화면 '최근 본 상품' 섹션에 사용."
    )
    @GetMapping("/products/recently-viewed")
    public ResponseEntity<ApiResponse<ProductSearchResponse>> getRecentlyViewed(
            @AuthenticationPrincipal UUID userId,
            @RequestParam(defaultValue = "10") int limit) {
        return ResponseEntity.ok(ApiResponse.success(productService.getRecentlyViewed(userId, limit)));
    }
}
