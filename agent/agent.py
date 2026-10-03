import os, sys, re, subprocess
from github import Github
import google.generativeai as genai

GH_TOKEN = os.environ["GH_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
REPO_NAME = os.environ.get("REPO_NAME", "mrtwister99-png/android-app-main")
AGENT_LABEL = os.environ.get("AGENT_LABEL", "android-logic")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)

issues = list(repo.get_issues(state="open", labels=[AGENT_LABEL]))
if not issues:
    print(f"No open issues with label {AGENT_LABEL} - exiting")
    sys.exit(0)

issue = issues[0]
print(f"Processing issue #{issue.number}: {issue.title}")

structure = []
for root, dirs, files in os.walk("main/app/src"):
    if "build" in root: continue
    for f in files[:30]:
        if f.endswith(".kt"):
            structure.append(os.path.join(root, f).replace("\\","/"))

prompt = f"""
You are expert Android Kotlin developer. Jetpack Compose, SDK 37, package com.example.newapp
REPO: {REPO_NAME}
ISSUE #{issue.number}: {issue.title}
BODY: {issue.body}
YOUR ROLE: {AGENT_LABEL}

Implement ONLY files for your role:
- android-ui: compose screens
- android-logic: ViewModels, logic
- android-api: Room entities, DAO, repository
- android-nav: navigation, gestures
- android-design: Theme.kt
- android-test: tests

Existing kt files: {chr(10).join(structure[:40])}

Output format MUST be:
FILE: app/src/main/java/com/example/newapp/...
```kotlin
code
```

Create max 4 files, concise, compilable.
"""

print("Calling Gemini...")
resp = model.generate_content(prompt)
text = resp.text
print(text[:4000])

pattern = re.compile(r'FILE:\s*(.+?)\n```(?:kotlin|java|xml|json)?\n(.*?)\n```', re.DOTALL)
matches = pattern.findall(text)
if not matches:
    print("No files found in Gemini output")
    sys.exit(1)

os.chdir("main")
subprocess.run(["git","config","user.name","Loyo Bot"], check=True)
subprocess.run(["git","config","user.email","bot@loyo.cz"], check=True)
branch = f"feature/{issue.number}-{AGENT_LABEL}"
subprocess.run(["git","checkout","-b",branch], check=True)

for path, content in matches:
    path = path.strip()
    full = os.path.join(os.getcwd(), path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full,"w",encoding="utf-8").write(content)
    print(f"Wrote {path}")

subprocess.run(["git","add","-A"], check=True)
subprocess.run(["git","commit","-m",f"[{AGENT_LABEL}] #{issue.number} {issue.title}"], check=True)
remote = f"https://x-access-token:{GH_TOKEN}@github.com/{REPO_NAME}.git"
subprocess.run(["git","push",remote,branch], check=True)

pr = repo.create_pull(title=f"[{AGENT_LABEL}] {issue.title} (#{issue.number})", body=f"Auto for #{issue.number}\n{issue.body}\nCloses #{issue.number}", head=branch, base="main")
issue.create_comment(f"Bot {AGENT_LABEL} created PR #{pr.number}")
print(f"Created PR {pr.number}")
