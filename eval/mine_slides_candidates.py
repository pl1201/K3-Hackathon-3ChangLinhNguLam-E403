import csv
import json
import re
import os
import pdfplumber
from collections import defaultdict

CSV_PATH = 'data/vlearn-pack/chatlog/chat_history_anonymized_for_hackathon.csv'
SLIDES = {
    "d1": 'data/vlearn-pack/slides/d1-slide-hackathon.pdf',
    "d2": 'data/vlearn-pack/slides/d2-slide-hackathon.pdf'
}
OUT_PATH = 'eval/chatlog-candidates-slides.json'

def extract_slides():
    slide_texts = {}
    for sid, path in SLIDES.items():
        if not os.path.exists(path):
            continue
        try:
            with pdfplumber.open(path) as pdf:
                pages = []
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append({
                        "page_num": i + 1,
                        "text": text
                    })
                slide_texts[sid] = pages
        except Exception as e:
            print(f"Error reading {path}: {e}")
    return slide_texts

def find_best_slide_match(student_msg, slide_texts):
    # Check if student mentions "trang X" or "slide X"
    match = re.search(r'(?i)(?:trang|slide)\s*(\d+)', student_msg)
    if match:
        page_num = int(match.group(1))
        # Need to determine if D1 or D2. Let's use simple keywords.
        is_d2 = re.search(r'(?i)agent|rag|prompt|context', student_msg)
        sid = "d2" if is_d2 else "d1"
        if sid in slide_texts and 1 <= page_num <= len(slide_texts[sid]):
            return sid, page_num, slide_texts[sid][page_num - 1]["text"]
            
    # Fallback keyword match against all slide pages
    # Simplistic: just find highest word overlap
    best_sid = None
    best_page = None
    best_text = None
    max_overlap = 0
    
    quote_match = re.search(r'đoạn được chọn:\s*"([^"]+)"', student_msg)
    quote = quote_match.group(1) if quote_match else student_msg
    words = set(re.sub(r'\W+', ' ', quote.lower()).split())
    if len(words) < 5:
        return None, None, None
        
    for sid, pages in slide_texts.items():
        for page in pages:
            p_words = set(re.sub(r'\W+', ' ', page["text"].lower()).split())
            overlap = len(words.intersection(p_words))
            if overlap > max_overlap and overlap > 5:
                max_overlap = overlap
                best_sid = sid
                best_page = page["page_num"]
                best_text = page["text"]
                
    if best_sid:
        return best_sid, best_page, best_text
    return None, None, None

def mine_candidates():
    print("Extracting text from slides...")
    slide_texts = extract_slides()
    
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
        sid, page_num, slide_text = find_best_slide_match(student_content, slide_texts)
        
        if sid:
            tutor_content = str(tutor_msgs[0]['content']) if tutor_msgs else ""
            candidates.append({
                "turn_id": turn_id,
                "slide_id": sid,
                "page_num": page_num,
                "student_message": student_content.replace('\n', ' ').strip(),
                "tutor_context": tutor_content.replace('\n', ' ').strip(),
                "slide_context": slide_text.replace('\n', ' ').strip()
            })
            
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
        
    print(f"\n=> Found {len(candidates)} candidates matching slides.")
    
    # Print a few to terminal
    for i, c in enumerate(candidates[:10]):
        print(f"\n[{i+1}] Turn: {c['turn_id']} - Slide: {c['slide_id']} Page: {c['page_num']}")
        print(f"Student: {c['student_message'][:150]}...")
        print(f"Slide context: {c['slide_context'][:150]}...")

if __name__ == '__main__':
    mine_candidates()
