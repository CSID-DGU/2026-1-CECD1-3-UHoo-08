package com.capstone.backend.domain.onboarding.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.UUID;

@Getter
@NoArgsConstructor
public class RegisteredProductBatchRequest {
    private List<UUID> productIds;
}
