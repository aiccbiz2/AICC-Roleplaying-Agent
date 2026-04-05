import os
import re

dir_path = "/Users/hh/Library/CloudStorage/GoogleDrive-davidlikessangria@gmail.com/My Drive/Python/082_Simulation_v3/docs/고객미팅_rawdata"

def analyze_file(filename):
    full_path = os.path.join(dir_path, filename)
    # Try different encodings
    for encoding in ['utf-8', 'utf-16', 'cp949']:
        try:
            with open(full_path, 'r', encoding=encoding) as f:
                content = f.read(2000) # Read more content
                break
        except:
            continue
    else:
        return {"old": filename, "error": "Could not decode file"}

    lines = [l.strip() for l in content.split('\n') if l.strip()]
    
    # Generic title "새로운 노트" or similar
    title = lines[0] if lines else "Unknown"
    
    # If the title is generic, look for context
    if "새로운 노트" in title or "회의녹취" in title or "미분류" in title or "AICC" in title:
        # Look for keywords in first 10 lines
        for line in lines[:15]:
            if any(kw in line for kw in ["회의", "소개", "미팅", "통화", "교육", "PoC", "포함", "논의"]):
                if not re.search(r'\d{4}\.\d{2}\.\d{2}', line) and len(line) > 2 and len(line) < 100:
                    title = line
                    break
        else:
            # If still not found, check for participant introductions
            for line in lines:
                if "참석자" in line or "책임님" in line or "LG 유플러스" in line:
                    # Snip some context
                    title = line[:50]
                    break

    is_internal = any(kw in content for kw in ["내부회의", "내부 회의", "내부 미팅", "우리끼리", "내부 논의"])
    
    # Date from filename
    date_match = re.match(r'(\d{8})', filename)
    date_prefix = date_match.group(1) if date_match else "unknown_date"
    
    return {
        "old": filename,
        "title": title,
        "is_internal": is_internal,
        "date": date_prefix,
        "raw_lines": lines[:10] # For debugging
    }

files = [f for f in os.listdir(dir_path) if "미분류" in f and f.endswith(".txt")]
results = []
for f in files:
    results.append(analyze_file(f))

import json
print(json.dumps(results, ensure_ascii=False, indent=2))
