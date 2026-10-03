import os, sys, re, subprocess
from github import Github
import google.generativeai as genai
GH_TOKEN = os.environ["GH_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
REPO_NAME = os.environ.get("REPO_NAME", "mrtwister99-png/android-app-main")
AGENT_LABEL = os.environ.get("AGENT_LABEL", "android-nav")
print(f"START {AGENT_LABEL} on {REPO_NAME}")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)
issues = list(repo.get_issues(state="open", labels=[AGENT_LABEL]))
if not issues:
    print(f"No open issues with label {AGENT_LABEL} - exit OK")
    sys.exit(0)
issue = issues[0]
print(f"Processing #{issue.number} {issue.title}")
structure=[]
for root,dirs,files in os.walk("main/app/src"):
    if "build" in root: continue
    for f in files[:20]:
        if f.endswith(".kt"): structure.append(os.path.join(root,f).replace("\\","/"))
prompt=f"Kotlin SDK37 com.example.newapp ISSUE #{issue.number}: {issue.title} BODY:{issue.body} ROLE:{AGENT_LABEL} Files:{chr(10).join(structure[:30])} Output FILE: app/src/... kotlin Max3"
resp=model.generate_content(prompt)
text=resp.text
print(text[:3000])
pattern=re.compile(r'FILE:\s*(.+?)\n```(?:kotlin)?\n(.*?)\n```', re.DOTALL)
matches=pattern.findall(text)
if not matches:
    print("No files"); sys.exit(1)
os.chdir("main")
subprocess.run(["git","config","user.name","Loyo Bot"], check=True)
subprocess.run(["git","config","user.email","bot@loyo.cz"], check=True)
branch=f"feature/{issue.number}-{AGENT_LABEL}"
subprocess.run(["git","branch","-D",branch], check=False)
subprocess.run(["git","checkout","-b",branch], check=True)
for path,content in matches:
    path=path.strip()
    full=os.path.join(os.getcwd(), path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full,"w",encoding="utf-8").write(content)
subprocess.run(["git","add","-A"], check=True)
subprocess.run(["git","commit","-m",f"[{AGENT_LABEL}] #{issue.number}"], check=True)
remote=f"https://x-access-token:{GH_TOKEN}@github.com/{REPO_NAME}.git"
subprocess.run(["git","push","-f",remote,branch], check=True)
pr=repo.create_pull(title=f"[{AGENT_LABEL}] {issue.title} (#{issue.number})", body=f"Closes #{issue.number}", head=branch, base="main")
issue.create_comment(f"PR #{pr.number}")
print(f"PR {pr.number} created")
