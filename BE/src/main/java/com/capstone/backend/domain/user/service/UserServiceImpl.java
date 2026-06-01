package com.capstone.backend.domain.user.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.pricetracking.repository.PriceTrackingRepository;
import com.capstone.backend.domain.onboarding.repository.RegisteredRepository;
import com.capstone.backend.domain.user.dto.response.OnboardingCompleteResponse;
import com.capstone.backend.domain.user.dto.response.ProfileUpdateResponse;
import com.capstone.backend.domain.user.dto.response.UserMeResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.entity.UserPreference;
import com.capstone.backend.domain.user.entity.UserSkinProfile;
import com.capstone.backend.domain.user.repository.UserPreferenceRepository;
import com.capstone.backend.domain.user.repository.UserRepository;
import com.capstone.backend.domain.user.repository.UserSkinProfileRepository;
import com.capstone.backend.domain.wishlist.repository.WishlistRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final UserSkinProfileRepository skinProfileRepository;
    private final UserPreferenceRepository preferenceRepository;
    private final WishlistRepository wishlistRepository;
    private final PriceTrackingRepository priceTrackingRepository;
    private final RegisteredRepository registeredRepository;
    private final WebClient webClient;

    @Value("${supabase.url}")
    private String supabaseUrl;

    @Value("${supabase.service-role-key}")
    private String supabaseServiceRoleKey;

    @Value("${supabase.storage-url}")
    private String supabaseStorageUrl;

    @Override
    @Transactional(readOnly = true)
    public UserMeResponse getMyInfo(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));

        UserSkinProfile skinProfile = skinProfileRepository.findByUserId(userId).orElse(null);
        UserPreference preference = preferenceRepository.findByUserId(userId).orElse(null);

        long wishlistCount = wishlistRepository.countByUserId(userId);
        long trackingCount = priceTrackingRepository.countByUserId(userId);
        long registeredCount = registeredRepository.countByUserId(userId);

        return UserMeResponse.of(user, skinProfile, preference, wishlistCount, trackingCount, registeredCount);
    }

    @Override
    public ProfileUpdateResponse updateMyProfile(UUID userId, String name, String gender, MultipartFile image) {
        String trimmedName = (name != null && !name.isBlank()) ? name.trim() : null;
        if (trimmedName != null && (trimmedName.length() < 2 || trimmedName.length() > 20)) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        if (image != null && !image.isEmpty() && image.getSize() > 5L * 1024 * 1024) {
            throw new BusinessException(ErrorCode.FILE_TOO_LARGE);
        }

        // 이미지 업로드는 트랜잭션 밖에서 먼저 처리
        String profileImageUrl = null;
        if (image != null && !image.isEmpty()) {
            profileImageUrl = uploadToSupabase(userId, image);
        }

        return saveProfile(userId, trimmedName, gender, profileImageUrl);
    }

    @Transactional
    protected ProfileUpdateResponse saveProfile(UUID userId, String name, String gender, String profileImageUrl) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updateProfile(name != null ? name.trim() : null, gender, profileImageUrl);
        return ProfileUpdateResponse.from(userRepository.save(user));
    }

    @Override
    @Transactional
    public OnboardingCompleteResponse completeOnboarding(UUID userId) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.completeOnboarding();
        User saved = userRepository.save(user);
        return new OnboardingCompleteResponse(true, saved.getUpdatedAt());
    }

    private String uploadToSupabase(UUID userId, MultipartFile image) {
        try {
            byte[] bytes = image.getBytes();
            String contentType = image.getContentType() != null ? image.getContentType() : "image/jpeg";
            String ext = contentType.contains("png") ? "png" : "jpg";
            String path = "/profile_image/" + userId + "." + ext;

            String uploadUrl = supabaseStorageUrl + path;
            log.info("[Storage] 업로드 시작: url={}, size={}, contentType={}", uploadUrl, bytes.length, contentType);

            webClient.post()
                    .uri(uploadUrl)
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + supabaseServiceRoleKey)
                    .header(HttpHeaders.CONTENT_TYPE, contentType)
                    .header("x-upsert", "true")
                    .bodyValue(bytes)
                    .retrieve()
                    .bodyToMono(String.class)
                    .block();

            String publicUrl = supabaseUrl + "/storage/v1/object/public" + path;
            log.info("[Storage] 업로드 성공: {}", publicUrl);
            return publicUrl;

        } catch (WebClientResponseException e) {
            log.error("[Storage] 업로드 실패: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        } catch (Exception e) {
            log.error("[Storage] 업로드 예외: {}", e.getMessage(), e);
            throw new BusinessException(ErrorCode.INTERNAL_ERROR);
        }
    }
}
