import os, re
from github import Github
import google.generativeai as genai

ISSUE_NUM = int(os.environ.get("ISSUE_NUMBER", "0"))
REPO_NAME = os.environ.get("REPO_NAME")
GH_TOKEN = os.environ.get("GH_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)
issue = repo.get_issue(ISSUE_NUM)
prompt_template = open("agent/prompt.md", encoding="utf-8").read()

full_prompt = f"{prompt_template}\n\nISSUE TITLE: {issue.title}\nISSUE BODY:\n{issue.body}"

resp = model.generate_content(full_prompt)
content = resp.text

# Simple parser: first file path in brackets or fallback
m = re.search(r"app/src/main/java/[^\s`]+\.kt", content)
if m:
    target_file = m.group(0)
else:
    # fallback for docs etc
    m2 = re.search(r"([\w/.-]+\.(kt|kts|md|yml))", content)
    target_file = m2.group(1) if m2 else f"app/src/main/java/com/example/newapp/Generated_{ISSUE_NUM}.kt"

# Clean markdown code fences
code = re.sub(r"```[\w]*\n", "", content)
code = re.sub(r"```", "", code)

# Write file locally
os.makedirs(os.path.dirname(target_file), exist_ok=True)
open(target_file, "w", encoding="utf-8").write(code)

# Create branch and PR
branch = f"bot/{os.path.basename(os.getcwd())}-{ISSUE_NUM}"
# ... (simplified, full logic is in your existing agent.py)
print(f"Generated {target_file} for issue {ISSUE_NUM}")
