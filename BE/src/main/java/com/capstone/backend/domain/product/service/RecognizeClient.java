package com.capstone.backend.domain.product.service;

import com.capstone.backend.common.exception.BusinessException;
import com.capstone.backend.common.exception.ErrorCode;
import com.capstone.backend.domain.product.dto.response.ProductRecognizeResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import java.time.Duration;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Component
@RequiredArgsConstructor
public class RecognizeClient {

    private final WebClient webClient;

    @Value("${ai.server-url}")
    private String aiServerUrl;

    public ProductRecognizeResponse recognize(String type, String data, UUID userId) {
        Map<String, Object> body = Map.of(
                "type", type,
                "data", data,
                "userId", userId.toString()
        );
        try {
            ProductRecognizeResponse response = webClient.post()
                    .uri(aiServerUrl + "/internal/recognize")
                    .bodyValue(body)
                    .retrieve()
                    .bodyToMono(ProductRecognizeResponse.class)
                    .timeout(Duration.ofSeconds(30))
                    .block();

            if (response == null) {
                throw new BusinessException(ErrorCode.AI_SERVER_ERROR);
            }
            return response;
        } catch (BusinessException e) {
            throw e;
        } catch (WebClientResponseException e) {
            log.error("FastAPI recognize 호출 실패: status={}, body={}", e.getStatusCode(), e.getResponseBodyAsString());
            throw new BusinessException(ErrorCode.AI_SERVER_ERROR);
        } catch (Exception e) {
            log.error("FastAPI recognize 호출 오류: {}", e.getMessage());
            throw new BusinessException(ErrorCode.AI_SERVER_ERROR);
        }
    }
}
