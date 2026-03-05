import sys
import io
import urllib.request
import urllib.error
import json
import base64
import os
import getpass

# Force UTF-8 stdout/stderr immediately (Windows cp1252 fix)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INCLUDE_EXTENSIONS = {'.html', '.jpg', '.jpeg', '.png', '.webp', '.css', '.js', '.md'}
EXCLUDE_FILES      = {'push_to_github.py'}

README_CONTENT = """\
# Mohamed Sathak A.J. College of Engineering - Ghibli Scrollytelling Landing Page

A premium, Awwwards-level scrollytelling landing page featuring:

- **168-frame scroll-linked animation** - A drone flies from the foreground toward the college entrance
- **Studio Ghibli x Architectural Realism** aesthetic - soft painterly tones, golden glows, spirit wisps
- **4 Scrollytelling Beats**: Tradition Meets Tech, The Vantage Point, Innovation in Bloom, Enter the Future
- **Spring-physics scroll smoothing** (stiffness: 80, damping: 25)
- **Particle / wisp system** that emerges at mid-scroll
- **Pure HTML/CSS/JS** - zero build step, opens directly in any browser

## Running Locally

```bash
# Option 1 - Python (recommended)
python -m http.server 8765
# then open: http://localhost:8765

# Option 2 - Open index.html in Chrome/Edge/Firefox
```

## Project Structure

```
index.html           - Complete landing page (single file)
ezgif-frame-001.jpg  |
ezgif-frame-002.jpg  |  168 drone-flight frames
...                  |  (scroll-linked canvas sequence)
ezgif-frame-168.jpg  |
```

## Design System

| Token          | Value        |
|----------------|--------------|
| Sky background | #e0f2f1      |
| Ghibli green   | #4caf84      |
| Ghibli gold    | #f0c060      |
| Ghibli rust    | #d4855a      |
| Ink            | #1a2030      |
| Fonts          | Lora + Inter |

## About the College

Mohamed Sathak A.J. College of Engineering, affiliated with Anna University,
is located in Siruseri, Chennai, Tamil Nadu. Established with a vision of
excellence, it offers B.E./B.Tech programs across multiple engineering
disciplines with a 95%+ placement rate.

---
Built with love - no frameworks, no dependencies, just the open web.
"""

HEADERS_BASE = {
    'Accept':               'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'Content-Type':         'application/json',
    'User-Agent':           'msajce-push-script/1.0',
}

def api(method, path, token, data=None, silent=False):
    url = 'https://api.github.com' + path
    headers = dict(HEADERS_BASE)
    headers['Authorization'] = 'Bearer ' + token
    body = json.dumps(data).encode() if data is not None else None
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode('utf-8', errors='replace')
        if not silent:
            print('\nGitHub API error %d: %s' % (e.code, err))
        raise

def main():
    print('\n+----------------------------------------------------------+')
    print('|  MSAJCE Ghibli Landing -> GitHub Push                   |')
    print('+----------------------------------------------------------+\n')

    token    = getpass.getpass('GitHub Personal Access Token (needs "repo" scope): ').strip()
    username = input('GitHub username: ').strip()
    repo     = input('Repo name [msajce-ghibli-landing]: ').strip() or 'msajce-ghibli-landing'
    priv_ans = input('Private repo? [y/N]: ').strip().lower()
    private  = (priv_ans == 'y')

    # Validate token
    print('\nValidating token...')
    try:
        me = api('GET', '/user', token)
    except Exception:
        print('ERROR: Could not authenticate. Check your token.')
        sys.exit(1)
    print('  Authenticated as: ' + me['login'])

    # Try to get existing repo; create if not found
    print('\nLooking up repo "%s/%s"...' % (username, repo))
    try:
        repo_info = api('GET', '/repos/%s/%s' % (username, repo), token, silent=True)
        print('  Repo already exists - will update files in it.')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print('  Repo not found - creating it now...')
            repo_info = api('POST', '/user/repos', token, {
                'name':        repo,
                'description': 'Premium Ghibli scrollytelling landing page - MSAJCE',
                'private':     private,
                'auto_init':   True,
            })
            print('  Created: ' + repo_info['html_url'])
        else:
            raise

    full_name      = repo_info['full_name']
    default_branch = repo_info.get('default_branch', 'main')

    # Get HEAD commit + tree SHA
    print('\nGetting HEAD of branch "%s"...' % default_branch)
    ref_info    = api('GET', '/repos/%s/git/ref/heads/%s' % (full_name, default_branch), token)
    base_commit = ref_info['object']['sha']
    base_tree   = api('GET', '/repos/%s/git/commits/%s' % (full_name, base_commit), token)['tree']['sha']
    print('  Base commit: ' + base_commit[:8])

    # Collect files
    files = [('README.md', README_CONTENT.encode('utf-8'), True)]
    all_entries = sorted(os.listdir(SCRIPT_DIR))
    for name in all_entries:
        if name in EXCLUDE_FILES:
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext not in INCLUDE_EXTENSIONS:
            continue
        fpath = os.path.join(SCRIPT_DIR, name)
        is_text = ext in {'.html', '.css', '.js', '.md', '.txt'}
        with open(fpath, 'rb') as f:
            files.append((name, f.read(), is_text))

    total = len(files)
    print('\nUploading %d files as Git blobs...' % total)

    tree_entries = []
    for idx, (name, content, is_text) in enumerate(files, 1):
        pct = int(idx / total * 100)
        filled = pct // 5
        bar = '#' * filled + '.' * (20 - filled)
        print('\r  [%s] %3d%%  %-50s' % (bar, pct, name[:50]), end='', flush=True)

        try:
            if is_text:
                blob = api('POST', '/repos/%s/git/blobs' % full_name, token, {
                    'content':  content.decode('utf-8', errors='replace'),
                    'encoding': 'utf-8',
                })
            else:
                blob = api('POST', '/repos/%s/git/blobs' % full_name, token, {
                    'content':  base64.b64encode(content).decode('ascii'),
                    'encoding': 'base64',
                })
        except Exception as ex:
            print('\nFailed to upload "%s": %s' % (name, ex))
            sys.exit(1)

        tree_entries.append({
            'path': name,
            'mode': '100644',
            'type': 'blob',
            'sha':  blob['sha'],
        })

    print('\n\nCreating Git tree...')
    new_tree = api('POST', '/repos/%s/git/trees' % full_name, token, {
        'base_tree': base_tree,
        'tree':      tree_entries,
    })
    print('  Tree SHA: ' + new_tree['sha'][:8])

    print('\nCreating commit...')
    new_commit = api('POST', '/repos/%s/git/commits' % full_name, token, {
        'message': 'Add MSAJCE Ghibli scrollytelling landing page\n\n'
                   '- 168-frame scroll-linked canvas animation\n'
                   '- Ghibli x Architectural Realism aesthetic\n'
                   '- 4 scrollytelling beats with spring physics\n'
                   '- Particle wisp system\n'
                   '- Pure HTML/CSS/JS, zero build step',
        'tree':    new_tree['sha'],
        'parents': [base_commit],
    })
    print('  Commit SHA: ' + new_commit['sha'][:8])

    print('\nUpdating branch "%s"...' % default_branch)
    api('PATCH', '/repos/%s/git/refs/heads/%s' % (full_name, default_branch), token, {
        'sha':   new_commit['sha'],
        'force': False,
    })

    repo_url  = repo_info['html_url']
    pages_url = 'https://%s.github.io/%s/' % (username, repo)

    print('\n+----------------------------------------------------------+')
    print('|  PUSHED SUCCESSFULLY!                                    |')
    print('+----------------------------------------------------------+')
    print('\n  Repository : ' + repo_url)
    print('  GitHub Pages: ' + pages_url)
    print('\n  To enable GitHub Pages (free hosting):')
    print('    repo Settings -> Pages -> Branch: main -> folder: / (root) -> Save')
    print()

if __name__ == '__main__':
    main()
