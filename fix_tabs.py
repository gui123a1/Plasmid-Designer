"""Fix VectorDetailView.vue tabs HTML - add missing </button> closing tags"""

import os

vue_path = os.path.join(
    os.path.dirname(__file__),
    'src', 'frontend', 'src', 'views', 'VectorDetailView.vue'
)

with open(vue_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the tabs section - the buttons are missing closing tags
# Pattern: <button ...>\n🗺️ 质粒图谱\n<button  (no </button> before next <button>)

# Replace the broken tabs section
old = """<div class="tabs">
<button
:class="['tab', { active: activeTab === 'map' }]"
@click="activeTab = 'map'"
>
🗺️ 质粒图谱
<button
:class="['tab', { active: activeTab === 'features' }]"
@click="activeTab = 'features'"
>
📋 元件列表
<button
:class="['tab', { active: activeTab === 'sequence' }]"
@click="activeTab = 'sequence'"
>
🧬 序列
</div>"""

new = """<div class="tabs">
<button
:class="['tab', { active: activeTab === 'map' }]"
@click="activeTab = 'map'"
>
🗺️ 质粒图谱
</button>
<button
:class="['tab', { active: activeTab === 'features' }]"
@click="activeTab = 'features'"
>
📋 元件列表
</button>
<button
:class="['tab', { active: activeTab === 'sequence' }]"
@click="activeTab = 'sequence'"
>
🧬 序列
</button>
</div>"""

if old in content:
    content = content.replace(old, new, 1)
    with open(vue_path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(content)
    print("Fixed: added </button> closing tags to VectorDetailView tabs")
else:
    # Try with different line endings
    old_crlf = old.replace('\n', '\r\n')
    if old_crlf in content:
        new_crlf = new.replace('\n', '\r\n')
        content = content.replace(old_crlf, new_crlf, 1)
        with open(vue_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(content)
        print("Fixed: added </button> closing tags to VectorDetailView tabs (CRLF)")
    else:
        print("WARNING: Could not find tabs pattern - may already be fixed or different format")
        # Search for the pattern
        idx = content.find("质粒图谱")
        if idx >= 0:
            print(f"Found '质粒图谱' at index {idx}")
            snippet = content[idx-50:idx+200]
            print(f"Context: {repr(snippet[:300])}")
