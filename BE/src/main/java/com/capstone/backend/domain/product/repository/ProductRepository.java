package com.capstone.backend.domain.product.repository;

import com.capstone.backend.domain.product.entity.Product;
import org.springframework.data.jpa.repository.JpaRepository;

import org.springframework.data.domain.Pageable;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ProductRepository extends JpaRepository<Product, UUID> {
    List<Product> findByCategory(String category);
    List<Product> findByNameContaining(String keyword);
    Optional<Product> findByNameAndBrand(String name, String brand);
    List<Product> findByNameContainingIgnoreCaseOrBrandContainingIgnoreCaseOrderByNameAsc(String name, String brand, Pageable pageable);
}
