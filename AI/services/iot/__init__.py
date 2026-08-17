"""
화담 CARE IoT 연산 계층.

아래 모듈이 순차 추가된다.
    psri.py                피부 환경 위험 지수 (절대습도 시간 적분)
    erl.py                 실질 잔여 수명 (Q10 열이력 적산)
    risk_score.py          제품별 점검 우선순위 종합 점수
    voc_anomaly.py         VOC 잔차 기반 이상 감지
    optical_delta.py       AS7341 기준값 대비 변화율
    event_detect.py        이벤트 판정 및 사용자 확인 연계
    inspection_protocol.py 카테고리별 점검 항목 규칙 테이블
"""