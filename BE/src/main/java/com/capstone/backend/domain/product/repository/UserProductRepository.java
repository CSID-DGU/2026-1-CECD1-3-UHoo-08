package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.UserProduct;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

public interface UserProductRepository extends JpaRepository<UserProduct, UUID> {
    boolean existsByUserIdAndProductId(UUID userId, UUID productId);

    @Modifying
    @Transactional
    @Query("DELETE FROM UserProduct up WHERE up.userId = :userId AND up.productId = :productId")
    void deleteByUserIdAndProductId(@Param("userId") UUID userId, @Param("productId") UUID productId);

    @Modifying
    @Transactional
    @Query("DELETE FROM UserProduct up WHERE up.userId = :userId AND up.productId = :productId AND up.usageType = :usageType")
    void deleteByUserIdAndProductIdAndUsageType(@Param("userId") UUID userId,
                                                @Param("productId") UUID productId,
                                                @Param("usageType") String usageType);

    @Query("SELECT up.productId FROM UserProduct up WHERE up.userId = :userId AND up.usageType = 'VIEWED' ORDER BY up.createdAt DESC")
    List<UUID> findRecentViewedProductIds(@Param("userId") UUID userId, Pageable pageable);
}
