package com.capstone.backend.domain.user.dto.response;

import com.capstone.backend.domain.user.entity.User;
import lombok.Builder;
import lombok.Getter;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.List;
import java.util.UUID;

@Getter
@Builder
public class UserMeResponse {

    private UUID id;
    private String name;
    private String email;
    private String profileImageUrl;
    private String gender;
    private String provider;
    private boolean onboardingCompleted;
    private SkinProfileInfo skinProfile;
    private PreferenceInfo preferences;
    private StatsInfo stats;

    @Getter
    @Builder
    public static class SkinProfileInfo {
        private String personalColor;
        private String skinType;
        private List<String> skinConcerns;
        private List<String> notes;
        private LocalDateTime updatedAt;
    }

    @Getter
    @Builder
    public static class PreferenceInfo {
        private Integer priceTolerancePercent;
        private String searchPurpose;
    }

    @Getter
    @Builder
    public static class StatsInfo {
        private long wishlistCount;
        private long trackingCount;
        private long registeredCount;
    }

    public static UserMeResponse of(User user, long wishlistCount, long trackingCount, long registeredCount) {
        SkinProfileInfo skinInfo = null;
        if (user.getSkinType() != null || user.getPersonalColor() != null) {
            skinInfo = SkinProfileInfo.builder()
                    .personalColor(user.getPersonalColor())
                    .skinType(user.getSkinType())
                    .skinConcerns(user.getSkinConcerns() != null
                            ? Arrays.asList(user.getSkinConcerns()) : List.of())
                    .notes(user.getNotes() != null
                            ? Arrays.asList(user.getNotes()) : null)
                    .updatedAt(user.getUpdatedAt())
                    .build();
        }

        PreferenceInfo prefInfo = null;
        if (user.getPriceTolerancePercent() != null || user.getSearchPurpose() != null) {
            prefInfo = PreferenceInfo.builder()
                    .priceTolerancePercent(user.getPriceTolerancePercent())
                    .searchPurpose(user.getSearchPurpose())
                    .build();
        }

        return UserMeResponse.builder()
                .id(user.getId())
                .name(user.getName())
                .email(user.getEmail())
                .profileImageUrl(user.getProfileImageUrl())
                .gender(user.getGender())
                .provider(user.getProvider())
                .onboardingCompleted(user.isOnboardingCompleted())
                .skinProfile(skinInfo)
                .preferences(prefInfo)
                .stats(StatsInfo.builder()
                        .wishlistCount(wishlistCount)
                        .trackingCount(trackingCount)
                        .registeredCount(registeredCount)
                        .build())
                .build();
    }
}
