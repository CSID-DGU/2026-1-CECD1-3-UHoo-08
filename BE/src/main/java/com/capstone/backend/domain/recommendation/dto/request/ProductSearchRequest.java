package com.capstone.backend.domain.recommendation.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class ProductSearchRequest {

    @NotBlank(message = "검색어를 입력해주세요")
    private String query;
}
