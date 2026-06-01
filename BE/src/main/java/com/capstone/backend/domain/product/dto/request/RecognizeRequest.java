package com.capstone.backend.domain.product.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class RecognizeRequest {

    @NotBlank(message = "type은 필수입니다.")
    private String type;   // IMAGE | NFC | TEXT

    @NotBlank(message = "data는 필수입니다.")
    private String data;   // base64 이미지 / NFC URL / 텍스트
}
