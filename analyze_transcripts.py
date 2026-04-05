import os
import re

dir_path = "/Users/hh/Library/CloudStorage/GoogleDrive-davidlikessangria@gmail.com/My Drive/Python/082_Simulation_v3/docs/고객미팅_rawdata"

def analyze_file(filename):
    full_path = os.path.join(dir_path, filename)
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read(500) # Read first 500 chars
            
            # Look for common header patterns
            # e.g. "신세계라이브_인소싱 소개"
            # e.g. "2026.03.06 금 오전 10:28"
            
            first_line = content.split('\n')[0].strip()
            lines = content.split('\n')
            
            title = first_line
            # If first line is a data/time, check second line
            if re.search(r'\d{4}\.\d{2}\.\d{2}', first_line):
                title = lines[1].strip() if len(lines) > 1 else first_line
            
            # Check for "내부회의" or "LG 유플러스" vs Customer
            is_internal = "내부회의" in content or "내부 회의" in content or "내부 미팅" in content
            
            # Try to extract date from filename if not in content
            date_match = re.match(r'(\d{8})', filename)
            date_prefix = date_match.group(1) if date_match else "unknown_date"
            
            return {
                "old": filename,
                "title": title,
                "is_internal": is_internal,
                "date": date_prefix
            }
    except Exception as e:
        return {"old": filename, "error": str(e)}

files = [f for f in os.listdir(dir_path) if "미분류" in f and f.endswith(".txt")]
results = []

for f in files:
    results.append(analyze_file(f))

for r in results:
    if "error" in r:
        print(f"Error in {r['old']}: {r['error']}")
        continue
    
    clean_title = re.sub(r'[\\/*?:"<>|]', "", r['title']).replace(" ", "_")
    entity = "내부" if r['is_internal'] else "고객" # Default placeholder, will refine
    
    # Try to find entity name in title
    # (e.g. "신세계라이브_인소싱_소개")
    suggested_name = f"{r['date']}_{clean_title}.txt"
    print(f"mv \"{r['old']}\" \"{suggested_name}\"")
