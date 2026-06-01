package com.capstone.backend.domain.onboarding.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.entity.ProductInsight;
import com.capstone.backend.domain.product.entity.UserProduct;
import com.capstone.backend.domain.product.repository.ProductInsightRepository;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.product.repository.UserProductRepository;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductAddRequest;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductAddResponse;
import com.capstone.backend.domain.onboarding.dto.RegisteredProductBatchRequest;
import com.capstone.backend.domain.onboarding.entity.Registered;
import com.capstone.backend.domain.onboarding.repository.RegisteredRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class RegisteredProductServiceImpl implements RegisteredProductService {

    private final ProductRepository productRepository;
    private final ProductInsightRepository productInsightRepository;
    private final UserProductRepository userProductRepository;
    private final RegisteredRepository registeredRepository;
    private final UserRepository userRepository;

    @Override
    @Transactional
    public RegisteredProductAddResponse addFavoriteItem(UUID userId, RegisteredProductAddRequest request) {
        // 1. 상품 조회 또는 신규 생성
        boolean isNewProduct = false;
        Product product = productRepository.findByNameAndBrand(request.getName(), request.getBrand())
                .orElse(null);

        if (product == null) {
            isNewProduct = true;
            LocalDateTime now = LocalDateTime.now();
            product = Product.builder()
                    .name(request.getName())
                    .brand(request.getBrand())
                    .category(request.getCategory())
                    .imageUrl(request.getImageUrl())
                    .originalPrice(request.getLowestPrice())
                    .build();
            product = productRepository.save(product);

            ProductInsight insight = ProductInsight.builder()
                    .product(product)
                    .lowestPrice(request.getLowestPrice())
                    .originalPrice(request.getLowestPrice())
                    .lastUpdatedAt(now)
                    .build();
            productInsightRepository.save(insight);
        }

        // 2. 중복 등록 확인
        if (registeredRepository.existsByUserIdAndProductId(userId, product.getId())) {
            throw new BusinessException(ErrorCode.ALREADY_REGISTERED);
        }

        // 3. registered_products 저장
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        Registered registered = Registered.builder()
                .user(user)
                .product(product)
                .createdAt(LocalDateTime.now())
                .build();
        registered = registeredRepository.save(registered);

        // 4. user_products 저장 (중복이면 SKIP)
        if (!userProductRepository.existsByUserIdAndProductId(userId, product.getId())) {
            UserProduct userProduct = UserProduct.builder()
                    .userId(userId)
                    .productId(product.getId())
                    .usageType("USING")
                    .createdAt(LocalDateTime.now())
                    .build();
            userProductRepository.save(userProduct);
        }

        return new RegisteredProductAddResponse(
                registered.getId(),
                product.getId(),
                product.getName(),
                product.getBrand(),
                product.getImageUrl(),
                isNewProduct
        );
    }

    @Override
    @Transactional
    public int saveBatch(UUID userId, RegisteredProductBatchRequest request) {
        if (request.getProductIds() == null || request.getProductIds().isEmpty()) return 0;

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        int saved = 0;
        for (UUID productId : request.getProductIds()) {
            Product product = productRepository.findById(productId).orElse(null);
            if (product == null) continue;

            if (!registeredRepository.existsByUserIdAndProductId(userId, productId)) {
                registeredRepository.save(Registered.builder()
                        .user(user)
                        .product(product)
                        .createdAt(LocalDateTime.now())
                        .build());
                saved++;
            }

            if (!userProductRepository.existsByUserIdAndProductId(userId, productId)) {
                userProductRepository.save(UserProduct.builder()
                        .userId(userId)
                        .productId(productId)
                        .usageType("ONBOARDING")
                        .createdAt(LocalDateTime.now())
                        .build());
            }
        }
        return saved;
    }

    @Override
    @Transactional
    public void removeFavoriteItem(UUID userId, UUID registeredId) {
        Registered registered = registeredRepository.findByIdAndUserId(registeredId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        UUID productId = registered.getProduct().getId();
        registeredRepository.delete(registered);
        userProductRepository.deleteByUserIdAndProductId(userId, productId);
    }
}
