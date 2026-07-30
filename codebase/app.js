document.addEventListener('DOMContentLoaded', () => {
    const btnGenerateQuiz = document.getElementById('btn-generate-quiz');
    const typingIndicator = document.getElementById('typing-indicator');
    const chatContainer = document.getElementById('chat-container');

    // MOCK DATA for Prototype CP-02
    const mockQuizData = {
        question: "Dựa vào tài liệu, nhóm AI nào chức năng chính là trả về content (nhạc, hình ảnh, mã code, ...) khi nhận prompt?",
        options: [
            { id: "opt1", text: "Discriminative AI" },
            { id: "opt2", text: "Generative AI" },
            { id: "opt3", text: "Agentic AI" },
            { id: "opt4", text: "Physical Model" }
        ],
        correctOption: "opt2",
        explanation: "Trong đoạn [T06-051], tài liệu nêu rõ: 'Nhóm thứ hai là generative AI: bản chất chức năng chính của nó là chúng ta prompt... nhưng nó trả về cho chúng ta cái content. Cái content này có thể là nhạc, có thể là hình ảnh, có thể là mã code...'",
        relatedSection: "[T06-051]"
    };

    btnGenerateQuiz.addEventListener('click', () => {
        // Add user message
        appendMessage('user', 'Tạo bài ôn tập ngay');
        
        // Remove button from first message
        btnGenerateQuiz.remove();

        // Show typing indicator
        typingIndicator.classList.remove('hidden');
        scrollToBottom();

        // Simulate AI Processing (Mock API call)
        setTimeout(() => {
            typingIndicator.classList.add('hidden');
            renderQuizBox(mockQuizData);
            scrollToBottom();
        }, 1500);
    });

    function appendMessage(sender, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${sender === 'user' ? 'user-message' : 'ai-message'}`;
        
        const avatarIcon = sender === 'user' ? 'fa-user' : 'fa-robot';
        
        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid ${avatarIcon}"></i></div>
            <div class="message-content">
                <p>${text}</p>
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
                <label class="option-label" for="${opt.id}">
                    <input type="radio" name="quiz-answer" id="${opt.id}" value="${opt.id}">
                    <span>${opt.text}</span>
                </label>
            `;
        });

        msgDiv.innerHTML = `
            <div class="avatar"><i class="fa-solid fa-robot"></i></div>
            <div class="message-content" style="width: 100%; max-width: 100%;">
                <p>Mình đã phân tích tài liệu và tạo câu hỏi trắc nghiệm. Hãy thử sức nhé:</p>
                <div class="quiz-box">
                    <div class="question-text">${quiz.question}</div>
                    <div class="options">
                        ${optionsHtml}
                    </div>
                    <button class="btn btn-secondary mt-3" id="btn-submit-quiz" disabled>Nộp bài</button>
                    <div id="feedback-result" class="feedback-box"></div>
                </div>
            </div>
        `;
        
        chatContainer.appendChild(msgDiv);
        attachQuizLogic(msgDiv, quiz);
    }

    function attachQuizLogic(container, quiz) {
        const radios = container.querySelectorAll('input[type="radio"]');
        const labels = container.querySelectorAll('.option-label');
        const btnSubmit = container.querySelector('#btn-submit-quiz');
        const feedbackBox = container.querySelector('#feedback-result');

        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                // Enable button
                btnSubmit.disabled = false;
                btnSubmit.classList.remove('btn-secondary');
                btnSubmit.classList.add('btn-primary');
                
                // Highlight selected
                labels.forEach(l => l.classList.remove('selected'));
                radio.closest('.option-label').classList.add('selected');
            });
        });

        btnSubmit.addEventListener('click', () => {
            const selectedRadio = container.querySelector('input[name="quiz-answer"]:checked');
            if (!selectedRadio) return;

            const selectedId = selectedRadio.value;
            const isCorrect = selectedId === quiz.correctOption;

            // Disable all inputs
            radios.forEach(r => r.disabled = true);
            btnSubmit.style.display = 'none';

            // Show right/wrong colors
            labels.forEach(label => {
                const input = label.querySelector('input');
                if (input.value === quiz.correctOption) {
                    label.classList.add('correct');
                } else if (input.checked && !isCorrect) {
                    label.classList.add('wrong');
                }
            });

            // Show feedback
            feedbackBox.classList.add('show');
            
            if (isCorrect) {
                feedbackBox.classList.add('all-correct');
                feedbackBox.innerHTML = `
                    <strong><i class="fa-solid fa-check-circle"></i> Chính xác!</strong>
                    <p>${quiz.explanation}</p>
                `;
            } else {
                feedbackBox.classList.add('gap-found');
                feedbackBox.innerHTML = `
                    <strong><i class="fa-solid fa-triangle-exclamation"></i> Chưa chính xác. Lỗ hổng kiến thức phát hiện!</strong>
                    <p>Bạn đang nhầm lẫn khái niệm. Hãy xem lại đoạn <strong>${quiz.relatedSection}</strong> bên trái.</p>
                    <p><em>Giải thích từ AI:</em> ${quiz.explanation}</p>
                `;
                
                // Simulate Gap Filler AI Action
                setTimeout(() => simulateGapFiller(), 2000);
            }
        });
    }

    function simulateGapFiller() {
        typingIndicator.classList.remove('hidden');
        scrollToBottom();
        
        setTimeout(() => {
            typingIndicator.classList.add('hidden');
            appendMessage('ai', 'Dường như bạn cần ôn lại phần Generative AI. Mình đã tạo một câu hỏi khác để kiểm tra lại phần này. Bạn sẵn sàng làm tiếp chứ?');
            scrollToBottom();
        }, 1500);
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
});
