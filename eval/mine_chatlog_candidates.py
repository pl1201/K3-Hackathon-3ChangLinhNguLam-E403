import csv
import json
import re
import os
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

CSV_PATH = 'data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv'
TRANSCRIPTS_DIR = 'data/vlearn-pack/transcript'
OUT_PATH = 'eval/chatlog-candidates.json'

KEYWORDS = {
    "transcript-01-clean": r'bài toán|pain|use case|ROI',
    "transcript-02-clean": r'metric|chỉ số|tự động hoá|automation level',
    "transcript-03-clean": r'ràng buộc|constraint',
    "transcript-04-clean": r'transformer|attention|agent|token',
    "transcript-05-clean": r'đánh giá|eval|dữ liệu|data',
    "transcript-06-clean": r'generative|discriminative|transformer|attention|token|next-token'
}

def load_transcripts():
    transcripts = {}
    for i in range(1, 7):
        lesson_id = f"transcript-{i:02d}-clean"
        file_path = os.path.join(TRANSCRIPTS_DIR, f"{lesson_id}.md")
        if not os.path.exists(file_path):
            continue
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract chunks: [T01-001] some text...
        chunks = []
        matches = list(re.finditer(r'\[(T\d{2}-\d+)\]', content))
        for j, match in enumerate(matches):
            chunk_id = match.group(1)
            start = match.end()
            end = matches[j+1].start() if j+1 < len(matches) else len(content)
            chunk_text = content[start:end].strip()
            chunks.append((chunk_id, chunk_text))
            
        transcripts[lesson_id] = {
            "content": content,
            "chunks": chunks,
            "pattern": re.compile(KEYWORDS[lesson_id], re.IGNORECASE)
        }
    return transcripts

def find_best_lesson(student_msg, transcripts):
    # Check if there is a direct quote
    quote_match = re.search(r'đoạn được chọn:\s*"([^"]+)"', student_msg)
    quote = quote_match.group(1) if quote_match else student_msg
    
    # Clean quote for comparison
    def clean(t): return re.sub(r'\W+', '', t.lower())
    clean_quote = clean(quote)
    
    best_lesson = None
    best_chunk = None
    max_overlap = 0
    
    # Strategy 1: Substring match of the quote in chunks
    if len(clean_quote) > 10:
        for lesson_id, data in transcripts.items():
            for chunk_id, chunk_text in data["chunks"]:
                clean_chunk = clean(chunk_text)
                if clean_quote in clean_chunk or clean_chunk in clean_quote:
                    return lesson_id, chunk_id
                
                # Approximate overlap based on word intersection
                quote_words = set(quote.lower().split())
                chunk_words = set(chunk_text.lower().split())
                overlap = len(quote_words.intersection(chunk_words))
                if overlap > max_overlap and overlap > 5:
                    max_overlap = overlap
                    best_lesson = lesson_id
                    best_chunk = chunk_id
                    
    if best_lesson:
        return best_lesson, best_chunk
        
    # Strategy 2: Keyword match
    matched_lessons = []
    for lesson_id, data in transcripts.items():
        if data["pattern"].search(student_msg):
            matched_lessons.append(lesson_id)
            
    if len(matched_lessons) == 1:
        return matched_lessons[0], None
    elif len(matched_lessons) > 1:
        # Resolve tie (e.g. 04 vs 06) by picking 06 by default or the last matched
        return matched_lessons[-1], None
        
    return None, None

def mine_candidates():
    print(f"Reading transcripts...")
    transcripts = load_transcripts()
    
    print(f"Reading {CSV_PATH}...")
    turns = defaultdict(list)
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            turns[row['turn_id']].append(row)
            
    candidates = []
    
    for turn_id, group in turns.items():
        student_msgs = [r for r in group if r['role'] == 'student']
        tutor_msgs = [r for r in group if r['role'] == 'tutor']
        
        if not student_msgs:
            continue
            
        student_content = str(student_msgs[0]['content'])
        lesson_id, chunk_id = find_best_lesson(student_content, transcripts)
        
        if lesson_id:
            tutor_content = str(tutor_msgs[0]['content']) if tutor_msgs else ""
            short_content = student_content[:250] + '...' if len(student_content) > 250 else student_content
            short_tutor = tutor_content[:200] + '...' if len(tutor_content) > 200 else tutor_content
            
            candidates.append({
                "turn_id": turn_id,
                "lesson_id": lesson_id,
                "chunk_id": chunk_id,
                "student_message": short_content.replace('\n', ' ').strip(),
                "tutor_context": short_tutor.replace('\n', ' ').strip(),
                "note": "TODO: correct / incorrect / ambiguous / unsupported"
            })

    # Save to JSON
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
        
    print(f"\n=> Đã lưu {len(candidates)} candidates vào {OUT_PATH}.")
    
    # Group by lesson to show distribution
    by_lesson = defaultdict(list)
    for c in candidates:
        by_lesson[c["lesson_id"]].append(c)
        
    print("\n========= PHÂN BỐ CANDIDATE THEO LESSON =========")
    for lid, cand_list in by_lesson.items():
        print(f"[{lid}]: {len(cand_list)} candidates")
        for i, c in enumerate(cand_list[:5]): # print up to 5 per lesson
            print(f"    - {c['turn_id']} (Chunk {c['chunk_id']}): {c['student_message'][:100]}...")
    print("\n=====================================================================")
    print("Vui lòng chọn ra 10-12 turn_id phù hợp nhất dàn trải trên các lesson để đưa vào golden-set nhé!")

if __name__ == '__main__':
    mine_candidates()
