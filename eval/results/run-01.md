# Kết quả chạy Eval (run-01)

**Tổng số case**: 32
**Pass**: 25/32 (78.1%)
**Số case bịa citation**: 0

## Theo Class
- **normal**: 7/11 (63.6%)
- **ambiguous**: 4/6 (66.7%)
- **domain**: 6/6 (100.0%)
- **out-of-scope**: 4/5 (80.0%)
- **source-truth**: 4/4 (100.0%)

## Theo Lesson
- **transcript-06-clean**: 19/21 (90.5%)
- **transcript-03-clean**: 3/5 (60.0%)
- **transcript-01-clean**: 1/2 (50.0%)
- **transcript-04-clean**: 0/2 (0.0%)
- **transcript-05-clean**: 1/1 (100.0%)
- **transcript-02-clean**: 1/1 (100.0%)

## Chi tiết Case
| ID | Lesson | Class | Expected | Actual | Pass | Ghi chú |
|---|---|---|---|---|---|---|
| normal-01 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-02 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-03 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-04 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-05 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-06 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-07 | transcript-06-clean | normal | correct | correct | ✅ |  |
| normal-08 | transcript-06-clean | normal | correct | incorrect | ❌ |  |
| ambiguous-01 | transcript-06-clean | ambiguous | ambiguous | ambiguous | ✅ |  |
| ambiguous-02 | transcript-06-clean | ambiguous | ambiguous | incorrect | ❌ |  |
| ambiguous-03 | transcript-06-clean | ambiguous | ambiguous | ambiguous | ✅ |  |
| ambiguous-04 | transcript-06-clean | ambiguous | ambiguous | ambiguous | ✅ |  |
| wrong-01 | transcript-06-clean | domain | incorrect | incorrect | ✅ |  |
| wrong-02 | transcript-06-clean | domain | incorrect | incorrect | ✅ |  |
| wrong-03 | transcript-06-clean | domain | incorrect | incorrect | ✅ |  |
| wrong-04 | transcript-06-clean | domain | incorrect | incorrect | ✅ |  |
| scope-01 | transcript-06-clean | out-of-scope | unsupported | unsupported | ✅ |  |
| scope-02 | transcript-06-clean | out-of-scope | unsupported | unsupported | ✅ |  |
| source-01 | transcript-06-clean | source-truth | incorrect | incorrect | ✅ |  |
| source-02 | transcript-06-clean | source-truth | incorrect | incorrect | ✅ |  |
| chatlog-01 | transcript-03-clean | domain | incorrect | incorrect | ✅ |  |
| chatlog-02 | transcript-03-clean | out-of-scope | unsupported | incorrect | ❌ |  |
| chatlog-03 | transcript-06-clean | out-of-scope | unsupported | unsupported | ✅ |  |
| chatlog-04 | transcript-03-clean | ambiguous | ambiguous | ambiguous | ✅ |  |
| chatlog-05 | transcript-03-clean | source-truth | incorrect | incorrect | ✅ |  |
| chatlog-06 | transcript-01-clean | source-truth | incorrect | incorrect | ✅ |  |
| chatlog-07 | transcript-04-clean | normal | correct | incorrect | ❌ |  |
| chatlog-08 | transcript-01-clean | normal | correct | incorrect | ❌ |  |
| chatlog-09 | transcript-04-clean | normal | correct | incorrect | ❌ |  |
| chatlog-10 | transcript-05-clean | out-of-scope | unsupported | unsupported | ✅ |  |
| chatlog-11 | transcript-03-clean | ambiguous | ambiguous | incorrect | ❌ |  |
| chatlog-12 | transcript-02-clean | domain | incorrect | incorrect | ✅ |  |