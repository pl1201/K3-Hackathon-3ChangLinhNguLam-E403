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


def get_bloom_prompt(level: str) -> PromptTemplate:
    """Get the appropriate PromptTemplate for a Bloom's Taxonomy level."""
    level = level.lower().strip()
    
    if level in ["remember", "nhận biết"]:
        template = _BLOOM_REMEMBER_TEMPLATE
    elif level in ["understand", "thông hiểu"]:
        template = _BLOOM_UNDERSTAND_TEMPLATE
    elif level in ["apply", "vận dụng"]:
        template = _BLOOM_APPLY_TEMPLATE
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
