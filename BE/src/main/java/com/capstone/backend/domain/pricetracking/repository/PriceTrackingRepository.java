package com.capstone.backend.domain.pricetracking.repository;

import com.capstone.backend.domain.pricetracking.entity.PriceTracking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface PriceTrackingRepository extends JpaRepository<PriceTracking, UUID> {

    List<PriceTracking> findByUserIdOrderByCreatedAtDesc(UUID userId);

    boolean existsByUserIdAndProductId(UUID userId, UUID productId);

    long countByUserId(UUID userId);

    @Query("SELECT pt FROM PriceTracking pt WHERE pt.id = :id AND pt.user.id = :userId")
    Optional<PriceTracking> findByIdAndUserId(@Param("id") UUID id, @Param("userId") UUID userId);

    @Query(value = """
            SELECT COALESCE(SUM(p.lowest_price - pt.target_price), 0)
            FROM price_trackings pt
            JOIN products p ON p.product_id = pt.product_id
            WHERE pt.user_id = :userId
              AND pt.is_achieved = true
              AND pt.achieved_at >= :monthStart
            """, nativeQuery = true)
    Long calculateMonthlySavings(@Param("userId") UUID userId,
                                 @Param("monthStart") LocalDateTime monthStart);

    @Modifying
    @Transactional
    @Query("DELETE FROM PriceTracking pt WHERE pt.id = :trackingId AND pt.user.id = :userId")
    int deleteByIdAndUserId(@Param("trackingId") UUID trackingId,
                            @Param("userId") UUID userId);

    @Modifying
    @Transactional
    @Query(value = """
            UPDATE price_trackings
            SET target_price = COALESCE(:targetPrice, target_price),
                alert_enabled = COALESCE(:alertEnabled, alert_enabled),
                updated_at = now()
            WHERE id = :trackingId AND user_id = :userId
            """, nativeQuery = true)
    int updateTracking(@Param("trackingId") UUID trackingId,
                       @Param("userId") UUID userId,
                       @Param("targetPrice") Integer targetPrice,
                       @Param("alertEnabled") Boolean alertEnabled);
}
