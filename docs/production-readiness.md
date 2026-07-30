# Production readiness

## Đã có trong vertical slice

- State machine LangGraph với state JSON-safe.
- LangChain structured output qua Pydantic.
- Citation allow-list: source ID phải thuộc context đã retrieval.
- Timeout và retry cho model.
- Langfuse callback theo graph invocation, `user_id`, `session_id`, tags và trace ID.
- Trace tree đã audit: `AGENT → RETRIEVER → GENERATION → GUARDRAIL`, không xuất
  các router/Runnable nội bộ không cần thiết.
- Export-stage masking che email và số điện thoại trước khi span rời ứng dụng.
- Generation ghi model, token usage, cache tokens, latency và cost; mỗi turn dùng
  một trace, toàn phiên dùng chung `session_id`.
- Feedback `user-thumbs` đã xác minh là score kiểu `BOOLEAN` gắn vào trace.
- Có kill switch riêng cho Langfuse Prompt Management; mặc định dùng prompt
  versioned trong code cho đến khi prompt `production` được tạo và bật rõ ràng.
- Feedback score `user-thumbs`.
- Mock fallback được hiển thị rõ trong UI.
- Health endpoint, regression tests và container chạy non-root.

## Bắt buộc trước production thật

1. Thay `InMemorySaver` và `SESSIONS` bằng Postgres checkpointer/store. Không chạy
   nhiều replica trước khi hoàn tất mục này.
2. Tích hợp SSO/auth của VLearn; `user_id` phải lấy từ token phía server, không nhận
   trực tiếp từ browser.
3. Rate limit theo user và tenant; giới hạn request body ở reverse proxy.
4. Mã hóa dữ liệu khi truyền/lưu, chính sách retention và quy trình xóa session.
5. Tắt `ENABLE_MOCK_FALLBACK` trong staging/production.
6. Chạy golden set bằng model thật, calibrate human-vs-judge và chặn release nếu
   hallucinated citation > 0.
7. Load test API, kiểm thử timeout/provider outage và xác minh retry không tạo
   request trùng.
8. Audit trace thật trong Langfuse: hierarchy, input/output tối thiểu, token/cost,
   prompt version, masking và score.
9. Pin image digest, dependency scanning, secret manager và rollback deployment.

## Quality gates đề xuất

| Gate | Bar |
|---|---:|
| Citation hợp lệ | 100% |
| Golden set tổng | ≥85% |
| P95 API (không tính cold start) | <8 giây |
| Provider error sau retry | <1% |
| Session start thành công | ≥99.5% |
| Trace chứa secret/PII thô | 0 |

Không gắn nhãn “production-ready” cho đến khi các mục bắt buộc có bằng chứng test
trong CI/staging.
