package com.capstone.backend.domain.user.dto.response;

import com.capstone.backend.domain.user.entity.User;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.UUID;

@Getter
@Builder
public class PreferenceResponse {

    private UUID userId;
    private String searchPurpose;
    private Integer priceTolerancePercent;
    private LocalDateTime updatedAt;

    public static PreferenceResponse from(User u) {
        return PreferenceResponse.builder()
                .userId(u.getId())
                .searchPurpose(u.getSearchPurpose())
                .priceTolerancePercent(u.getPriceTolerancePercent())
                .updatedAt(u.getUpdatedAt())
                .build();
    }
}
