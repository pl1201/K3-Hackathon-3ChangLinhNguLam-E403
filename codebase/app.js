document.addEventListener('DOMContentLoaded', () => {
    const chatInput = document.getElementById('chat-input');
    const btnSend = document.getElementById('btn-send');
    const typingIndicator = document.getElementById('typing-indicator');
    const chatContainer = document.getElementById('chat-container');

    let expectingFollowUp = false;

    // MOCK DATA for Prototype CP-02
    const mockQuizData1 = {
        question: "Dựa vào tài liệu, nhóm AI nào chức năng chính là trả về content (nhạc, hình ảnh, mã code, ...) khi nhận prompt?",
        options: [
            { id: "opt1", text: "Discriminative AI" },
            { id: "opt2", text: "Generative AI" },
            { id: "opt3", text: "Agentic AI" },
            { id: "opt4", text: "Physical Model" }
        ],
        correctOption: "opt2",
        explanation: "Trong đoạn [T06-051], tài liệu nêu rõ: 'Nhóm thứ hai là generative AI: bản chất chức năng chính của nó là chúng ta prompt... nhưng nó trả về cho chúng ta cái content...'",
        relatedSection: "[T06-051]"
    };

    const mockQuizData2 = {
        question: "Trong kiến trúc hệ thống, vai trò cơ bản của AI phân loại (Discriminative AI) là gì?",
        options: [
            { id: "opt1", text: "Tự lên kế hoạch và thao tác như người thật" },
            { id: "opt2", text: "Phân loại, dự đoán, gán nhãn cho dữ liệu (ví dụ: phát hiện gian lận)" },
            { id: "opt3", text: "Tạo ra một bộ não có suy nghĩ" },
            { id: "opt4", text: "Sáng tác một bài thơ hoặc một bức ảnh" }
        ],
        correctOption: "opt2",
        explanation: "Trong đoạn [T06-051], tài liệu nêu rõ: 'Nhóm đầu tiên là cái gọi là discriminative AI — nói một tiếng là phân loại, dự đoán...'",
        relatedSection: "[T06-051]"
    };

    // Auto-resize textarea
    chatInput.addEventListener('input', () => {
        chatInput.style.height = 'auto';
        chatInput.style.height = chatInput.scrollHeight + 'px';
    });

    // Enter to send (Shift+Enter for newline)
    chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    });

    btnSend.addEventListener('click', handleSend);

    function handleSend() {
        const text = chatInput.value.trim();
        if (!text) return;

        appendMessage('user', text);
        chatInput.value = '';
        chatInput.style.height = 'auto';

        typingIndicator.classList.remove('hidden');
        scrollToBottom();

        // Simulate AI Processing (Mock API call)
        setTimeout(() => {
            typingIndicator.classList.add('hidden');
            processUserIntent(text.toLowerCase());
        }, 1200);
    }

    function processUserIntent(text) {
        if (expectingFollowUp && (text.includes('có') || text.includes('ok') || text.includes('tiếp') || text.includes('làm'))) {
            expectingFollowUp = false;
            appendMessage('ai', 'Tuyệt vời. Đây là câu hỏi để giúp bạn củng cố kiến thức:');
            renderQuizBox(mockQuizData2);
        } else if (text.includes('tóm tắt')) {
            expectingFollowUp = false;
            appendMessage('ai', `
                <p><strong>Tóm tắt kiến thức (Đoạn T06-051):</strong></p>
                <ul>
                    <li><strong>Discriminative AI:</strong> AI Phân loại/Dự đoán. Dùng để gán nhãn dữ liệu (ví dụ phát hiện gian lận).</li>
                    <li><strong>Generative AI:</strong> AI Sinh tạo. Dùng để tạo ra nội dung (nhạc, code, ảnh) dựa vào prompt.</li>
                    <li><strong>Agentic AI:</strong> Có khả năng tự lên kế hoạch và hành động để đạt mục tiêu cụ thể.</li>
                </ul>
                <p>Bạn đã nắm rõ phần này chưa? Bạn có muốn mình tạo một bài quiz nhỏ không?</p>
            `);
        } else if (text.includes('quiz') || text.includes('hỏi') || text.includes('trắc nghiệm')) {
            expectingFollowUp = false;
            appendMessage('ai', 'Dựa trên tài liệu bên trái, mình đã soạn câu hỏi trắc nghiệm sau cho bạn:');
            renderQuizBox(mockQuizData1);
        } else {
            appendMessage('ai', 'Xin lỗi, mình chưa rõ ý của bạn. Bạn muốn mình <strong>tóm tắt</strong> kiến thức hay <strong>tạo quiz</strong> trắc nghiệm?');
        }
        scrollToBottom();
    }

    function appendMessage(sender, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;
        
        const avatarIcon = sender === 'user' ? 'fa-user' : 'fa-robot';
        
        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid ${avatarIcon}"></i></div>
            <div class="message-content">
                ${sender === 'user' ? `<p>${text}</p>` : text}
            </div>
        `;
        chatContainer.appendChild(msgDiv);
    }

    function renderQuizBox(quiz) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ai-message`;
        
        let optionsHtml = '';
        quiz.options.forEach(opt => {
            optionsHtml += `
                <label class="option-label" for="${opt.id}-${quiz.correctOption}">
                    <input type="radio" name="quiz-answer-${quiz.correctOption}" id="${opt.id}-${quiz.correctOption}" value="${opt.id}">
                    <span>${opt.text}</span>
                </label>
            `;
        });

        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content" style="width: 100%; max-width: 100%;">
                <div class="quiz-box" style="margin-top: 0;">
                    <div class="question-text">${quiz.question}</div>
                    <div class="options">
                        ${optionsHtml}
                    </div>
                    <button class="btn btn-secondary mt-3 btn-submit-quiz" disabled>Nộp bài</button>
                    <div class="feedback-box"></div>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(msgDiv);
        attachQuizLogic(msgDiv, quiz);
    }

    function attachQuizLogic(container, quiz) {
        const radios = container.querySelectorAll('input[type="radio"]');
        const labels = container.querySelectorAll('.option-label');
        const btnSubmit = container.querySelector('.btn-submit-quiz');
        const feedbackBox = container.querySelector('.feedback-box');

        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                btnSubmit.disabled = false;
                btnSubmit.classList.remove('btn-secondary');
                btnSubmit.classList.add('btn-primary');
                
                labels.forEach(l => l.classList.remove('selected'));
                radio.closest('.option-label').classList.add('selected');
            });
        });

        btnSubmit.addEventListener('click', () => {
            const selectedRadio = container.querySelector('input[type="radio"]:checked');
            if (!selectedRadio) return;

            const selectedId = selectedRadio.value;
            const isCorrect = selectedId === quiz.correctOption;

            radios.forEach(r => r.disabled = true);
            btnSubmit.style.display = 'none';

            labels.forEach(label => {
                const input = label.querySelector('input');
                if (input.value === quiz.correctOption) {
                    label.classList.add('correct');
                } else if (input.checked && !isCorrect) {
                    label.classList.add('wrong');
                }
            });

            feedbackBox.classList.add('show');
            
            if (isCorrect) {
                expectingFollowUp = false;
                feedbackBox.classList.add('all-correct');
                feedbackBox.innerHTML = `
                    <strong><i class="fa-solid fa-check-circle"></i> Chính xác!</strong>
                    <p>${quiz.explanation}</p>
                `;
            } else {
                expectingFollowUp = true;
                feedbackBox.classList.add('gap-found');
                feedbackBox.innerHTML = `
                    <strong><i class="fa-solid fa-triangle-exclamation"></i> Chưa chính xác. Lỗ hổng kiến thức phát hiện!</strong>
                    <p>Bạn đang nhầm lẫn khái niệm. Hãy xem lại đoạn <strong>${quiz.relatedSection}</strong> bên trái.</p>
                    <p><em>Giải thích từ AI:</em> ${quiz.explanation}</p>
                    <hr style="border-color: rgba(0,0,0,0.1); margin: 10px 0;">
                    <p style="margin-top:10px;">Bạn có muốn mình tạo 1 câu hỏi khác để kiểm tra lại phần này không?</p>
                `;
            }
            scrollToBottom();
        });
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});
