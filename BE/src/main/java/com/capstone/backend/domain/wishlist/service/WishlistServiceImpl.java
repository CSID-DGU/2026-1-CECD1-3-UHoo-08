package com.capstone.backend.domain.wishlist.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.entity.Product;
import com.capstone.backend.domain.product.repository.ProductRepository;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.capstone.backend.domain.wishlist.dto.WishlistAddRequest;
import com.capstone.backend.domain.wishlist.dto.WishlistAddResponse;
import com.capstone.backend.domain.wishlist.dto.WishlistItemResponse;
import com.capstone.backend.domain.wishlist.dto.WishlistListResponse;
import com.capstone.backend.domain.wishlist.entity.Wishlist;
import com.capstone.backend.domain.wishlist.repository.WishlistRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class WishlistServiceImpl implements WishlistService {

    private final WishlistRepository wishlistRepository;
    private final ProductRepository productRepository;
    private final UserRepository userRepository;

    @Override
    @Transactional
    public WishlistAddResponse addWishlist(UUID userId, WishlistAddRequest request) {
        if (wishlistRepository.existsByUserIdAndProductId(userId, request.getProductId())) {
            throw new BusinessException(ErrorCode.ALREADY_WISHLISTED);
        }

        Product product = productRepository.findById(request.getProductId())
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        Wishlist wishlist = Wishlist.builder()
                .user(user)
                .product(product)
                .createdAt(LocalDateTime.now())
                .build();

        return WishlistAddResponse.from(wishlistRepository.save(wishlist));
    }

    @Override
    @Transactional(readOnly = true)
    public WishlistListResponse getWishlists(UUID userId, int page, int size) {
        Page<Wishlist> pageResult = wishlistRepository
                .findByUser_IdOrderByCreatedAtDesc(userId, PageRequest.of(page - 1, size));

        List<WishlistItemResponse> items = pageResult.getContent().stream()
                .map(WishlistItemResponse::of)
                .collect(Collectors.toList());

        return new WishlistListResponse(items, pageResult.getTotalElements());
    }

    @Override
    @Transactional
    public void removeWishlist(UUID userId, UUID wishlistId) {
        Wishlist wishlist = wishlistRepository.findByIdAndUserId(wishlistId, userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        wishlistRepository.delete(wishlist);
    }
}
