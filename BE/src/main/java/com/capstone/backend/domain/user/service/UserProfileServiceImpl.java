package com.capstone.backend.domain.user.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.user.dto.request.PreferencesRequest;
import com.capstone.backend.domain.user.dto.request.PreferenceUpdateRequest;
import com.capstone.backend.domain.user.dto.request.SkinProfileRequest;
import com.capstone.backend.domain.user.dto.request.SkinProfileUpdateRequest;
import com.capstone.backend.domain.user.dto.response.PreferenceResponse;
import com.capstone.backend.domain.user.dto.response.SkinProfileResponse;
import com.capstone.backend.domain.user.entity.User;
import com.capstone.backend.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class UserProfileServiceImpl implements UserProfileService {

    private final UserRepository userRepository;

    @Override
    @Transactional
    public SkinProfileResponse saveSkinProfile(UUID userId, SkinProfileRequest request) {
        if (!request.isValid()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        String[] concerns = toArray(request.getSkinConcerns());
        String[] notes = toArray(request.getNotes());
        user.updateSkinProfile(request.getPersonalColor(), request.getSkinType(),
                concerns != null ? concerns : new String[0], notes);
        return SkinProfileResponse.from(userRepository.save(user));
    }

    @Override
    @Transactional
    public SkinProfileResponse updateSkinProfile(UUID userId, SkinProfileUpdateRequest request) {
        if (!request.isValid()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updateSkinProfile(request.getPersonalColor(), request.getSkinType(),
                toArray(request.getSkinConcerns()), toArray(request.getNotes()));
        return SkinProfileResponse.from(userRepository.save(user));
    }

    @Override
    @Transactional
    public PreferenceResponse savePreferences(UUID userId, PreferencesRequest request) {
        if (!request.isValid()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updatePreferences(null, request.getPriceTolerancePercent());
        return PreferenceResponse.from(userRepository.save(user));
    }

    @Override
    @Transactional
    public PreferenceResponse updatePreferences(UUID userId, PreferenceUpdateRequest request) {
        if (!request.isValid()) {
            throw new BusinessException(ErrorCode.VALIDATION_ERROR);
        }
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new BusinessException(ErrorCode.NOT_FOUND));
        user.updatePreferences(request.getSearchPurpose(), request.getPriceTolerancePercent());
        return PreferenceResponse.from(userRepository.save(user));
    }

    private String[] toArray(List<String> list) {
        return list == null ? null : list.toArray(new String[0]);
    }
}
