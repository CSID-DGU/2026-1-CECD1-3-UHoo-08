package com.capstone.backend.domain.pricetracking.dto.response;

import com.capstone.backend.domain.user.entity.User;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;

@Getter
@Builder
public class AlertSettingsResponse {
    private boolean targetPriceAlert;
    private boolean weeklyReport;
    private LocalDateTime updatedAt;

    public static AlertSettingsResponse from(User u) {
        return AlertSettingsResponse.builder()
                .targetPriceAlert(u.isTargetPriceAlert())
                .weeklyReport(u.isWeeklyReport())
                .updatedAt(u.getUpdatedAt())
                .build();
    }

    public static AlertSettingsResponse defaultSettings() {
        return AlertSettingsResponse.builder()
                .targetPriceAlert(true)
                .weeklyReport(false)
                .updatedAt(null)
                .build();
    }
}
