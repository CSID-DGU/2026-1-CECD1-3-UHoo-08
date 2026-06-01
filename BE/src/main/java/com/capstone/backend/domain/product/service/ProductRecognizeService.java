package com.capstone.backend.domain.product.service;

import com.capstone.backend.domain.product.dto.request.RecognizeRequest;
import com.capstone.backend.domain.product.dto.response.ProductRecognizeResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.UUID;

@Service
@RequiredArgsConstructor
public class ProductRecognizeService {

    private final RecognizeClient recognizeClient;

    public ProductRecognizeResponse recognize(UUID userId, RecognizeRequest request) {
        return recognizeClient.recognize(
                request.getType().toUpperCase(),
                request.getData(),
                userId
        );
    }
}
