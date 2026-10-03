import os, sys, re, subprocess, time
from github import Github
from github.Auth import Token

GH_TOKEN = os.environ["GH_TOKEN"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
REPO_NAME = os.environ.get("REPO_NAME", "mrtwister99-png/android-app-main")
AGENT_LABEL = os.environ.get("AGENT_LABEL", "android-design")
print(f"START {AGENT_LABEL} on {REPO_NAME}")

from google import genai
from google.genai.errors import ClientError
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
MUST OUTPUT:
FILE: app/src/main/java/com/example/newapp/ui/theme/Theme.kt
```kotlin
code
```
"""

# MODELY S NEJVYSSI FREE QUOTOU - SERAZENE PODLE LIMITU
models_to_try = [
    "gemini-flash-lite-latest",      # 4000 req/min - nejvyssi free
    "models/gemini-flash-lite-latest",
    "gemini-2.5-flash-lite",         # 4000 req/min, 4M tokens
    "models/gemini-2.5-flash-lite",
    "gemini-flash-latest",           # 1000 req/min
    "models/gemini-flash-latest",
    "gemini-2.5-flash",              # 1000 req/min, 1M tokens
    "models/gemini-2.5-flash",
    "gemini-3-flash-preview",        # preview ma vetsi quota nez 3.8
    "models/gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "models/gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "models/gemini-3.1-flash-lite",
]

text = None
used_model = None
for model_name in models_to_try:
    for attempt in range(2):  # 2 pokusy na model
        try:
            print(f"Trying {model_name} attempt {attempt+1}")
            resp = client.models.generate_content(model=model_name, contents=prompt)
            text = resp.text
            used_model = model_name
            print(f"OK {model_name} len={len(text)}")
            break
        except Exception as e:
            err_str = str(e)
            print(f"FAIL {model_name}: {err_str[:500]}")
            # 429 = quota - zkus dalsi model hned, necekaj 14h
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                print(f"Quota hit for {model_name}, switching to next model...")
                time.sleep(2)
                break
            # 503 = overloaded - pockej a zkus znovu
            if "503" in err_str or "UNAVAILABLE" in err_str:
                print(f"Overloaded {model_name}, retry in 5s...")
                time.sleep(5)
                continue
            # 404 = model not found - dalsi
            if "404" in err_str:
                break
    if text:
        break

if not text:
    print("All high-quota models failed, listing:")
    for m in client.models.list(): print(f" - {m.name}")
    sys.exit(1)

print(text[:5000])
pattern=re.compile(r'FILE:\s*(.+?)\s*\n```(?:kotlin|java)?\n(.*?)\n```', re.DOTALL | re.IGNORECASE)
matches=pattern.findall(text)
if not matches:
    print("Fallback - code blocks without FILE")
    code_blocks=re.findall(r'```(?:kotlin|java)?\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if code_blocks:
        base="app/src/main/java/com/example/newapp/ui/theme/Theme.kt"
        for i,code in enumerate(code_blocks[:3]):
            p=base if i==0 else base.replace(".kt", f"{i}.kt")
            matches.append((p,code))

if not matches:
    print("No FILE blocks"); print(text); sys.exit(1)

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
    print(f"WROTE {path}")

subprocess.run(["git","add","-A"], check=True)
subprocess.run(["git","commit","-m",f"[{AGENT_LABEL}] #{issue.number}"], check=True)
remote=f"https://x-access-token:{GH_TOKEN}@github.com/{REPO_NAME}.git"
subprocess.run(["git","push","-f",remote,branch], check=True)
pr=repo.create_pull(title=f"[{AGENT_LABEL}] {issue.title} (#{issue.number})", body=f"Closes #{issue.number} Model:{used_model}", head=branch, base="main")
issue.create_comment(f"PR #{pr.number} {pr.html_url} via {used_model}")
print(f"PR {pr.number} OK via {used_model}")
