package com.capstone.backend.domain.product.dto.response;

import com.fasterxml.jackson.annotation.JsonInclude;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.util.UUID;

@Getter
@Setter
@NoArgsConstructor
@JsonInclude(JsonInclude.Include.NON_NULL)
public class ProductRecognizeResponse {
    private UUID productId;
    private String name;
    private String brand;
    private Object featureJson;
    private Object geminiPrice;
    private Object reviewSummary;
}
