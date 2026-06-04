package com.capstone.backend.domain.product.entity;

import io.hypersistence.utils.hibernate.type.json.JsonType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "products")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class Product {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "product_id")
    private UUID id;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "brand", nullable = false)
    private String brand;

    @Column(name = "category", nullable = false)
    private String category;

    @Column(name = "image_url")
    private String imageUrl;

    @Column(name = "original_price")
    private Integer originalPrice;

    // ── 상품 특성 (구 product_features) ──────────────────────────────
    @Type(JsonType.class)
    @Column(name = "feature_json", columnDefinition = "jsonb")
    private String featureJson;

    // ── 가격·리뷰 인사이트 (구 product_insights) ─────────────────────
    @Column(name = "lowest_price")
    private Integer lowestPrice;

    @Column(name = "savings")
    private Integer savings;

    @Type(JsonType.class)
    @Column(name = "stores", columnDefinition = "jsonb")
    private String stores;

    @Column(name = "review_summary")
    private String reviewSummary;

    @Column(name = "average_score")
    private BigDecimal averageScore;

    @Column(name = "review_count")
    private Integer reviewCount;

    @Type(JsonType.class)
    @Column(name = "skin_type_satisfaction", columnDefinition = "jsonb")
    private String skinTypeSatisfaction;

    @Column(name = "last_updated_at")
    private LocalDateTime lastUpdatedAt;

    public void updatePriceData(Integer lowestPrice, String stores, LocalDateTime lastUpdatedAt) {
        this.lowestPrice = lowestPrice;
        this.stores = stores;
        this.lastUpdatedAt = lastUpdatedAt;
    }
}
