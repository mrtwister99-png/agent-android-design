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

# JASNY PROMPT S PRIKLADEM
prompt=f"""You are Kotlin Android dev, SDK 37, package com.example.newapp
ISSUE #{issue.number}: {issue.title}
BODY: {issue.body}
ROLE: {AGENT_LABEL}

EXISTING FILES:
{chr(10).join(structure[:35])}

YOU MUST OUTPUT ONLY IN THIS EXACT FORMAT - NO EXCEPTIONS:

FILE: app/src/main/java/com/example/newapp/ui/theme/Theme.kt
```kotlin
package com.example.newapp.ui.theme
...
code here
```

FILE: app/src/main/java/com/example/newapp/ui/screen/YourScreen.kt
```kotlin
...
```

Rules:
- Start each file with FILE: path on its own line
- Then kotlin block
- Max 3 files
- Keep package com.example.newapp
- Fix the issue.
"""

models_to_try = [
    "gemini-3.8-flash",
    "models/gemini-3.8-flash",
    "gemini-3.7-flash",
    "models/gemini-3.7-flash",
    "gemini-3.6-flash",
    "models/gemini-3.6-flash",
    "gemini-3.5-flash",
    "models/gemini-3.5-flash",
]

text = None
used_model = None
for model_name in models_to_try:
    try:
        print(f"Trying {model_name}")
        resp = client.models.generate_content(model=model_name, contents=prompt)
        text = resp.text
        used_model = model_name
        print(f"OK {model_name} len={len(text)}")
        break
    except Exception as e:
        print(f"FAIL {model_name}: {e}")
        continue

if not text:
    print("All models failed, listing:")
    for m in client.models.list(): print(m.name)
    sys.exit(1)

print(text[:5000])

# 1. POKUS - standard FILE: blok
pattern = re.compile(r'FILE:\s*(.+?)\s*\n```(?:kotlin|java)?\n(.*?)\n```', re.DOTALL | re.IGNORECASE)
matches = pattern.findall(text)

# 2. POKUS - kdyz chybi FILE: ale je tam kotlin blok, vezmi ho a odhadni cestu
if not matches:
    print("No FILE blocks with regex1, trying fallback...")
    # najdi vsechny kotlin bloky
    code_blocks = re.findall(r'```(?:kotlin|java)?\n(.*?)\n```', text, re.DOTALL | re.IGNORECASE)
    if code_blocks:
        print(f"Found {len(code_blocks)} code blocks without FILE header, guessing paths...")
        # podle AGENT_LABEL odhadni cestu
        base_guess = {
            "android-design": "app/src/main/java/com/example/newapp/ui/theme/Theme.kt",
            "android-ui": "app/src/main/java/com/example/newapp/ui/screen/MainScreen.kt",
            "android-nav": "app/src/main/java/com/example/newapp/navigation/NavHost.kt",
            "android-logic": "app/src/main/java/com/example/newapp/logic/Logic.kt",
            "android-api": "app/src/main/java/com/example/newapp/data/Api.kt",
        }
        guess_path = base_guess.get(AGENT_LABEL, f"app/src/main/java/com/example/newapp/{AGENT_LABEL.replace('android-','')}/Generated.kt")
        for i, code in enumerate(code_blocks[:3]):
            # pokud je vic bloku, rozlis
            p = guess_path if i==0 else guess_path.replace(".kt", f"{i}.kt")
            matches.append((p, code))
            print(f"Guessed {p}")

# 3. POKUS - kdyz ani bloky nejsou, vezmi cely text jako kod (tvuj pripad z obrazku)
if not matches:
    print("Still no blocks, taking whole output as kotlin file...")
    # odstran pripadne importy a vezmi cely
    clean = text.strip()
    if "import" in clean and "package" in clean:
        guess_path = f"app/src/main/java/com/example/newapp/{AGENT_LABEL.replace('android-','')}/Generated.kt"
        matches = [(guess_path, clean)]
        print(f"Using whole text as {guess_path}")

if not matches:
    print("No FILE blocks after all fallbacks")
    print(text)
    sys.exit(1)

print(f"Will write {len(matches)} files")
os.chdir("main")
subprocess.run(["git","config","user.name","Loyo Bot"], check=True)
subprocess.run(["git","config","user.email","bot@loyo.cz"], check=True)
branch=f"feature/{issue.number}-{AGENT_LABEL}"
subprocess.run(["git","branch","-D",branch], check=False)
subprocess.run(["git","checkout","-b",branch], check=True)

for path,content in matches:
    path=path.strip().lstrip("/").strip()
    # security - musi byt uvnitr app/src
    if not path.startswith("app/src"):
        path = f"app/src/main/java/com/example/newapp/{os.path.basename(path)}"
    full=os.path.join(os.getcwd(), path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full,"w",encoding="utf-8").write(content)
    print(f"WROTE {path} ({len(content)} chars)")

subprocess.run(["git","add","-A"], check=True)
subprocess.run(["git","commit","-m",f"[{AGENT_LABEL}] #{issue.number} {issue.title}"], check=True)
remote=f"https://x-access-token:{GH_TOKEN}@github.com/{REPO_NAME}.git"
subprocess.run(["git","push","-f",remote,branch], check=True)
pr=repo.create_pull(title=f"[{AGENT_LABEL}] {issue.title} (#{issue.number})", body=f"Closes #{issue.number}\nModel: {used_model}", head=branch, base="main")
issue.create_comment(f"PR #{pr.number} {pr.html_url} via {used_model}")
print(f"PR {pr.number} OK via {used_model}")
