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
public class SkinProfileResponse {

    private UUID userId;
    private String personalColor;
    private String skinType;
    private List<String> skinConcerns;
    private List<String> notes;
    private LocalDateTime updatedAt;

    public static SkinProfileResponse from(User u) {
        return SkinProfileResponse.builder()
                .userId(u.getId())
                .personalColor(u.getPersonalColor())
                .skinType(u.getSkinType())
                .skinConcerns(u.getSkinConcerns() != null ? Arrays.asList(u.getSkinConcerns()) : List.of())
                .notes(u.getNotes() != null ? Arrays.asList(u.getNotes()) : null)
                .updatedAt(u.getUpdatedAt())
                .build();
    }
}
