package com.capstone.backend.domain.user.entity;

import io.hypersistence.utils.hibernate.type.array.StringArrayType;
import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.Type;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@Table(name = "users")
@EntityListeners(AuditingEntityListener.class)
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    @Column(name = "id")
    private UUID id;

    @Column(name = "email", unique = true)
    private String email;

    @Column(name = "password_hash")
    private String passwordHash;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "profile_image_url")
    private String profileImageUrl;

    @Column(name = "gender", length = 10)
    private String gender;

    @Column(name = "provider", nullable = false)
    private String provider;

    @Column(name = "provider_id")
    private String providerId;

    @Column(name = "fcm_token")
    private String fcmToken;

    @Builder.Default
    @Column(name = "onboarding_completed", nullable = false)
    private boolean onboardingCompleted = false;

    // ── 피부 프로필 (구 user_skin_profiles) ──────────────────────────
    @Column(name = "personal_color", length = 20)
    private String personalColor;

    @Column(name = "skin_type", length = 20)
    private String skinType;

    @Type(StringArrayType.class)
    @Builder.Default
    @Column(name = "skin_concerns", columnDefinition = "text[]")
    private String[] skinConcerns = new String[0];

    @Type(StringArrayType.class)
    @Column(name = "notes", columnDefinition = "text[]")
    private String[] notes;

    // ── 취향 설정 (구 user_preferences) ─────────────────────────────
    @Column(name = "search_purpose", length = 20)
    private String searchPurpose;

    @Column(name = "price_tolerance_percent")
    private Integer priceTolerancePercent;

    // ── 알림 설정 (구 price_tracking_alert_settings) ─────────────────
    @Builder.Default
    @Column(name = "target_price_alert", nullable = false)
    private boolean targetPriceAlert = true;

    @Builder.Default
    @Column(name = "weekly_report", nullable = false)
    private boolean weeklyReport = false;

    @CreatedDate
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    public void updateFcmToken(String fcmToken) {
        this.fcmToken = fcmToken;
    }

    public void completeOnboarding() {
        this.onboardingCompleted = true;
    }

    public void updateProfile(String name, String gender, String profileImageUrl) {
        if (name != null) this.name = name;
        if (gender != null) this.gender = gender;
        if (profileImageUrl != null) this.profileImageUrl = profileImageUrl;
    }

    public void updateSkinProfile(String personalColor, String skinType, String[] skinConcerns, String[] notes) {
        if (personalColor != null) this.personalColor = personalColor;
        if (skinType != null) this.skinType = skinType;
        if (skinConcerns != null) this.skinConcerns = skinConcerns;
        if (notes != null) this.notes = notes;
    }

    public void updatePreferences(String searchPurpose, Integer priceTolerancePercent) {
        if (searchPurpose != null) this.searchPurpose = searchPurpose;
        if (priceTolerancePercent != null) this.priceTolerancePercent = priceTolerancePercent;
    }

    public void updateAlertSettings(Boolean targetPriceAlert, Boolean weeklyReport) {
        if (targetPriceAlert != null) this.targetPriceAlert = targetPriceAlert;
        if (weeklyReport != null) this.weeklyReport = weeklyReport;
    }
}
