import os, sys, re, subprocess
from github import Github
from github.Auth import Token

GH_TOKEN = os.environ["GH_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
REPO_NAME = os.environ.get("REPO_NAME", "mrtwister99-png/android-app-main")
AGENT_LABEL = os.environ.get("AGENT_LABEL", "android-nav")
print(f"START {AGENT_LABEL} on {REPO_NAME}")

from google import genai
client = genai.Client(api_key=GEMINI_API_KEY)

g = Github(auth=Token(GH_TOKEN))
repo = g.get_repo(REPO_NAME)

issues = list(repo.get_issues(state="open", labels=[AGENT_LABEL]))
if not issues:
    print(f"No open issues {AGENT_LABEL}"); sys.exit(0)

issue = issues[0]
print(f"Processing #{issue.number} {issue.title}")

structure=[]
for root,dirs,files in os.walk("main/app/src"):
    if "build" in root: continue
    for f in files[:25]:
        if f.endswith(".kt"): structure.append(os.path.join(root,f).replace("\\","/"))

prompt=f"""Kotlin Android SDK 37 com.example.newapp
ISSUE #{issue.number}: {issue.title}
BODY: {issue.body}
ROLE: {AGENT_LABEL}
Files: {chr(10).join(structure[:35])}
Output max 3 FILE: app/src/... with ```kotlin
"""

# PRESNE PODLE SCREENSHOTU + TVUJ POZADAVEK
models_to_try = [
    "gemini-3.8-flash",
    "models/gemini-3.8-flash",
    "gemini-3.7-flash",
    "models/gemini-3.7-flash",
    "gemini-3.6-flash",
    "models/gemini-3.6-flash",
    "gemini-3.5-flash",
    "models/gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "models/gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "models/gemini-3.1-flash-lite",
]

text = None
last_err = None
for model_name in models_to_try:
    try:
        print(f"Trying {model_name}")
        resp = client.models.generate_content(model=model_name, contents=prompt)
        text = resp.text
        print(f"OK with {model_name} -> {len(text)} chars")
        break
    except Exception as e:
        print(f"FAIL {model_name}: {e}")
        last_err = e
        continue

if not text:
    print("Vsechny modely selhaly, listuju dostupne:")
    try:
        for m in client.models.list():
            print(f" - {m.name}")
    except Exception as e:
        print(f"List failed: {e}")
    print(f"Last error: {last_err}")
    sys.exit(1)

print(text[:4000])
import re
pattern=re.compile(r'FILE:\s*(.+?)\n```(?:kotlin)?\n(.*?)\n```', re.DOTALL)
matches=pattern.findall(text)
if not matches:
    print("No FILE blocks"); sys.exit(1)

os.chdir("main")
subprocess.run(["git","config","user.name","Loyo Bot"], check=True)
subprocess.run(["git","config","user.email","bot@loyo.cz"], check=True)
branch=f"feature/{issue.number}-{AGENT_LABEL}"
subprocess.run(["git","branch","-D",branch], check=False)
subprocess.run(["git","checkout","-b",branch], check=True)
for path,content in matches:
    path=path.strip().lstrip("/")
    if not path.startswith("app/src"): path=f"app/src/main/java/com/example/newapp/{os.path.basename(path)}"
    full=os.path.join(os.getcwd(), path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full,"w",encoding="utf-8").write(content)
    print(f"Wrote {path}")

subprocess.run(["git","add","-A"], check=True)
subprocess.run(["git","commit","-m",f"[{AGENT_LABEL}] #{issue.number}"], check=True)
remote=f"https://x-access-token:{GH_TOKEN}@github.com/{REPO_NAME}.git"
subprocess.run(["git","push","-f",remote,branch], check=True)
pr=repo.create_pull(title=f"[{AGENT_LABEL}] {issue.title} (#{issue.number})", body=f"Closes #{issue.number} using {model_name}", head=branch, base="main")
issue.create_comment(f"PR #{pr.number} {pr.html_url} via {model_name}")
print(f"PR {pr.number} OK via {model_name}")
