"""Bloom's Taxonomy Prompt Templates.

Provides Few-Shot templates to guide the LLM in generating questions 
across different cognitive levels of Bloom's Taxonomy.
"""

from langchain_core.prompts import PromptTemplate

# 1. Level: Remember (Nhận biết)
_BLOOM_REMEMBER_TEMPLATE = """
Mức độ: NHẬN BIẾT (Remember) - Yêu cầu học viên nhớ lại định nghĩa, sự kiện, khái niệm cơ bản.
Ví dụ: "Khái niệm X là gì?", "Ai là người phát minh ra Y?"

Nội dung kiến thức:
{context_text}

Hãy tạo ra {num_questions} câu hỏi trắc nghiệm ở mức độ NHẬN BIẾT.
"""

# 2. Level: Understand (Thông hiểu)
_BLOOM_UNDERSTAND_TEMPLATE = """
Mức độ: THÔNG HIỂU (Understand) - Yêu cầu học viên giải thích, phân loại, tóm tắt hoặc so sánh.
Ví dụ: "Đâu là điểm khác biệt chính giữa X và Y?", "Đoạn mã sau thực hiện chức năng gì?"

Nội dung kiến thức:
{context_text}

Hãy tạo ra {num_questions} câu hỏi trắc nghiệm ở mức độ THÔNG HIỂU.
"""

# 3. Level: Apply (Vận dụng)
_BLOOM_APPLY_TEMPLATE = """
Mức độ: VẬN DỤNG (Apply) - Yêu cầu học viên áp dụng kiến thức vào một tình huống thực tế cụ thể.
Ví dụ: "Trong dự án phần mềm A, khách hàng yêu cầu tính năng B, bạn nên sử dụng mẫu thiết kế nào?", "Với input X, thuật toán Y sẽ trả về kết quả nào?"

Nội dung kiến thức:
{context_text}

Hãy tạo ra {num_questions} câu hỏi trắc nghiệm ở mức độ VẬN DỤNG bằng cách đưa ra các tình huống.
"""

# 4. Level: Analyze (Phân tích)
_BLOOM_ANALYZE_TEMPLATE = """
Mức độ: PHÂN TÍCH (Analyze) - Yêu cầu học viên phân tách thông tin thành các thành phần, tìm mối liên hệ hoặc cấu trúc.
Ví dụ: "Tại sao thuật toán X lại hiệu quả hơn Y trong trường hợp này?", "Hãy xác định lỗi logic trong đoạn code sau."

Nội dung kiến thức:
{context_text}

Hãy tạo ra {num_questions} câu hỏi trắc nghiệm ở mức độ PHÂN TÍCH.
"""

# 5. Level: Evaluate (Đánh giá)
_BLOOM_EVALUATE_TEMPLATE = """
Mức độ: ĐÁNH GIÁ (Evaluate) - Yêu cầu học viên đưa ra quyết định, phán đoán hoặc lập luận bảo vệ quan điểm.
Ví dụ: "Đánh giá ưu nhược điểm của công nghệ X so với công nghệ Y trong dự án lớn.", "Tại sao giải pháp A lại phù hợp hơn giải pháp B trong bối cảnh này?"

Nội dung kiến thức:
{context_text}

Hãy tạo ra {num_questions} câu hỏi trắc nghiệm ở mức độ ĐÁNH GIÁ.
"""


def get_bloom_prompt(level: str) -> PromptTemplate:
    """Get the appropriate PromptTemplate for a Bloom's Taxonomy level."""
    level = level.lower().strip()
    
    if level in ["remember", "nhận biết"]:
        template = _BLOOM_REMEMBER_TEMPLATE
    elif level in ["understand", "thông hiểu"]:
        template = _BLOOM_UNDERSTAND_TEMPLATE
    elif level in ["apply", "vận dụng"]:
        template = _BLOOM_APPLY_TEMPLATE
    elif level in ["analyze", "phân tích"]:
        template = _BLOOM_ANALYZE_TEMPLATE
    elif level in ["evaluate", "đánh giá"]:
        template = _BLOOM_EVALUATE_TEMPLATE
    else:
        # Fallback to standard generation
        template = (
            "Nội dung kiến thức:\n{context_text}\n\n"
            "Hãy tạo ra {num_questions} câu hỏi trắc nghiệm."
        )
        
    return PromptTemplate(
        input_variables=["context_text", "num_questions"],
        template=template,
    )
