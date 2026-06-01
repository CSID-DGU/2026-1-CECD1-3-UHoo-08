package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.ProductFeature;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ProductFeatureRepository extends JpaRepository<ProductFeature, UUID> {
    Optional<ProductFeature> findByProduct_Id(UUID productId);
}
