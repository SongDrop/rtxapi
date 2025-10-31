#!/bin/bash

# ===============================================
# GitHub Issue Search VS Code Extension Generator
# ===============================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           GitHub Issue Search Extension Generator             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Ask for extension name
read -p "Enter your GitHub Issue Search extension folder name (default: github-issue-search): " EXTNAME
EXTNAME=${EXTNAME:-github-issue-search}

# Check if folder exists
if [ -d "$EXTNAME" ]; then
    read -p "Folder '$EXTNAME' already exists. Remove it? (y/N): " REMOVE
    REMOVE=${REMOVE:-N}
    if [[ "$REMOVE" == "y" || "$REMOVE" == "Y" ]]; then
        echo "Removing existing folder '$EXTNAME'..."
        rm -rf "$EXTNAME"
    else
        echo "Exiting to avoid overwriting."
        exit 1
    fi
fi

echo "Creating extension in folder: $EXTNAME"
mkdir -p "$EXTNAME/src" "$EXTNAME/media"
cd "$EXTNAME" || exit

# Download logo
echo -e "${CYAN}📥 Downloading Github logo...${NC}"
curl -s -o media/logo.png "https://i.postimg.cc/pLxdTbkj/github-mark.png"

# Create package.json
cat <<EOL > package.json
{
  "name": "github-issue-search",
  "displayName": "GitHub Issue Search",
  "description": "Search GitHub issues for solutions and error messages",
  "publisher": "github-search",
  "version": "1.0.0",
  "icon": "media/logo.png",
  "engines": {
    "vscode": "^1.81.0"
  },
  "categories": [
    "Other"
  ],
  "activationEvents": [
    "onCommand:github-issue-search.search"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {
        "command": "github-issue-search.search",
        "title": "Search GitHub Issues",
        "category": "GitHub"
      }
    ],
    "configuration": {
      "title": "GitHub Issue Search",
      "properties": {
        "githubIssueSearch.githubToken": {
          "type": "string",
          "description": "GitHub Personal Access Token (optional, for higher rate limits)",
          "scope": "application"
        },
        "githubIssueSearch.defaultRepo": {
          "type": "string",
          "default": "makeplane/plane",
          "description": "Default repository to search (format: owner/repo)",
          "scope": "application"
        }
      }
    }
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./"
  },
  "devDependencies": {
    "@types/vscode": "^1.81.0",
    "@types/node": "16.x",
    "typescript": "^4.9.4"
  }
}
EOL

# Create tsconfig.json
cat <<EOL > tsconfig.json
{
  "compilerOptions": {
    "module": "commonjs",
    "target": "ES2020",
    "outDir": "out",
    "lib": ["ES2020"],
    "sourceMap": true,
    "rootDir": "src",
    "strict": true
  }
}
EOL

# Create the extension source
cat <<'EOL' > src/extension.ts
import * as vscode from 'vscode';
import * as https from 'https';

interface GitHubIssue {
    title: string;
    body: string;
    html_url: string;
    number: number;
    state: string;
    created_at: string;
}

export function activate(context: vscode.ExtensionContext) {
    console.log('GitHub Issue Search extension is now active!');

    let disposable = vscode.commands.registerCommand('github-issue-search.search', async () => {
        // Get configuration
        const config = vscode.workspace.getConfiguration('githubIssueSearch');
        const defaultRepo = config.get('defaultRepo') as string;
        const githubToken = config.get('githubToken') as string;

        // Ask for repository
        const repoInput = await vscode.window.showInputBox({
            placeHolder: `Enter repository (owner/repo)`,
            value: defaultRepo,
            prompt: 'Which GitHub repository do you want to search?'
        });

        if (!repoInput) {
            return;
        }

        // Ask for search query
        const query = await vscode.window.showInputBox({
            placeHolder: 'Enter search terms (e.g., "minio upload error", "500 internal server error")',
            prompt: 'What issue are you looking for?'
        });

        if (!query) {
            return;
        }

        // Show progress
        await vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `Searching GitHub issues in ${repoInput}...`,
            cancellable: false
        }, async (progress) => {
            progress.report({ increment: 0 });

            try {
                const issues = await searchGitHubIssues(repoInput, query, githubToken);
                progress.report({ increment: 100 });

                if (issues.length === 0) {
                    vscode.window.showInformationMessage(`No issues found for "${query}" in ${repoInput}`);
                    return;
                }

                // Show results in quick pick
                const items = issues.map(issue => ({
                    label: `#${issue.number}: ${issue.title}`,
                    description: `State: ${issue.state}`,
                    detail: issue.body.substring(0, 200) + '...',
                    issue: issue
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: `Found ${issues.length} issues. Select one to view details:`,
                    matchOnDetail: true,
                    matchOnDescription: true
                });

                if (selected) {
                    // Show issue details
                    const issue = selected.issue;
                    const panel = vscode.window.createWebviewPanel(
                        'githubIssue',
                        `Issue #${issue.number}: ${issue.title}`,
                        vscode.ViewColumn.One,
                        {
                            enableScripts: true,
                            localResourceRoots: []
                        }
                    );

                    panel.webview.html = getIssueWebviewContent(issue);
                    
                    // Add button to open in browser
                    vscode.window.showInformationMessage(
                        `Issue #${issue.number}: ${issue.title}`,
                        'Open in Browser',
                        'Copy URL'
                    ).then(selection => {
                        if (selection === 'Open in Browser') {
                            vscode.env.openExternal(vscode.Uri.parse(issue.html_url));
                        } else if (selection === 'Copy URL') {
                            vscode.env.clipboard.writeText(issue.html_url);
                            vscode.window.showInformationMessage('Issue URL copied to clipboard!');
                        }
                    });
                }

            } catch (error: any) {
                vscode.window.showErrorMessage(`Search failed: ${error.message}`);
            }
        });
    });

    context.subscriptions.push(disposable);
}

async function searchGitHubIssues(repo: string, query: string, token?: string): Promise<GitHubIssue[]> {
    return new Promise((resolve, reject) => {
        const [owner, repoName] = repo.split('/');
        if (!owner || !repoName) {
            reject(new Error('Invalid repository format. Use: owner/repo'));
            return;
        }

        const searchQuery = `repo:${owner}/${repoName} ${query} in:title,body`;
        const encodedQuery = encodeURIComponent(searchQuery);
        
        const options = {
            hostname: 'api.github.com',
            path: `/search/issues?q=${encodedQuery}&sort=updated&order=desc&per_page=20`,
            method: 'GET',
            headers: {
                'User-Agent': 'VSCode-GitHub-Issue-Search',
                'Accept': 'application/vnd.github.v3+json'
            }
        };

        if (token) {
            (options.headers as any)['Authorization'] = `token ${token}`;
        }

        let data = '';

        const req = https.request(options, (res) => {
            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                if (res.statusCode === 200) {
                    try {
                        const result = JSON.parse(data);
                        resolve(result.items || []);
                    } catch (parseError) {
                        reject(new Error('Failed to parse GitHub API response'));
                    }
                } else if (res.statusCode === 403) {
                    reject(new Error('GitHub API rate limit exceeded. Consider adding a GitHub token in settings.'));
                } else {
                    reject(new Error(`GitHub API error: ${res.statusCode} - ${data}`));
                }
            });
        });

        req.on('error', (error) => {
            reject(error);
        });

        req.setTimeout(10000, () => {
            req.destroy();
            reject(new Error('Request timeout'));
        });

        req.end();
    });
}

function getIssueWebviewContent(issue: GitHubIssue): string {
    return `
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Issue #${issue.number}</title>
            <style>
                body {
                    font-family: var(--vscode-font-family);
                    font-size: var(--vscode-font-size);
                    color: var(--vscode-foreground);
                    background: var(--vscode-editor-background);
                    padding: 20px;
                    line-height: 1.5;
                }
                .issue-header {
                    border-bottom: 1px solid var(--vscode-panel-border);
                    padding-bottom: 15px;
                    margin-bottom: 20px;
                }
                .issue-title {
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                    color: var(--vscode-foreground);
                }
                .issue-meta {
                    font-size: 12px;
                    color: var(--vscode-descriptionForeground);
                    margin-bottom: 10px;
                }
                .issue-body {
                    background: var(--vscode-input-background);
                    border: 1px solid var(--vscode-input-border);
                    border-radius: 4px;
                    padding: 15px;
                    white-space: pre-wrap;
                    font-family: var(--vscode-font-family);
                    max-height: 400px;
                    overflow-y: auto;
                }
                .issue-link {
                    color: var(--vscode-textLink-foreground);
                    text-decoration: none;
                }
                .issue-link:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <div class="issue-header">
                <div class="issue-title">${escapeHtml(issue.title)}</div>
                <div class="issue-meta">
                    #${issue.number} • ${issue.state} • Created: ${new Date(issue.created_at).toLocaleDateString()}
                </div>
                <a href="${issue.html_url}" class="issue-link" target="_blank">Open on GitHub</a>
            </div>
            <div class="issue-body">${escapeHtml(issue.body)}</div>
        </body>
        </html>
    `;
}

function escapeHtml(unsafe: string): string {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

export function deactivate() {}
EOL

# Create .vscodeignore
cat <<EOL > .vscodeignore
.vscode
src
*.ts
*.map
.git
.gitignore
*.sh
node_modules
EOL

# Create README.md - FIXED: Properly escaped to avoid command execution
cat <<'EOL' > README.md
# GitHub Issue Search VS Code Extension

Search GitHub issues directly from VS Code to find solutions to problems.

## Features

- 🔍 Search issues in any GitHub repository
- 📋 View issue details directly in VS Code
- 🌐 Open issues in browser with one click
- ⚡ Fast search with GitHub API
- 🔑 Optional GitHub token for higher rate limits

## Usage

1. **Open Command Palette** (Ctrl+Shift+P / Cmd+Shift+P)
2. **Search for "Search GitHub Issues"**
3. **Enter repository** (e.g., makeplane/plane)
4. **Enter search query** (e.g., "minio upload error")

## Configuration

### GitHub Token (Optional)
For higher rate limits, add a GitHub Personal Access Token:

1. Go to [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens)
2. Generate a new token with public_repo scope
3. In VS Code Settings, search for "GitHub Issue Search"
4. Add your token to githubIssueSearch.githubToken

### Default Repository
Set a default repository to search:
- In Settings, set githubIssueSearch.defaultRepo to your preferred repository

## Examples

### Search for MinIO Issues
- Repository: makeplane/plane
- Query: minio upload s3 error

### Search for Specific Errors
- Repository: makeplane/plane  
- Query: "500 internal server error" file upload

### Search by Feature
- Repository: makeplane/plane
- Query: authentication login bug

## Keyboard Shortcut

Add this to your keybindings.json for quick access:

\`\`\`json
{
    "key": "ctrl+shift+g",
    "command": "github-issue-search.search"
}
\`\`\`

## Rate Limits

- Without token: 60 requests/hour
- With token: 5000 requests/hour

## Support

For issues with the extension itself, please report them on the extension's GitHub repository.
EOL

echo -e "${GREEN}✅ GitHub Issue Search extension created in '$EXTNAME'${NC}"


# -----------------------------
# Create License.md (MIT License)
# -----------------------------
cat <<EOL > LICENSE.md
MIT License

Copyright (c) $(date +%Y) Gabriel Majorsky

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
EOL

# ===============================================
# Build and Install Extension
# ===============================================

echo -e "${CYAN}🔨 Building and installing extension...${NC}"

# Set Node options
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
export NODE_OPTIONS=--openssl-legacy-provider

echo -e "${YELLOW}Node: $(node -v) | npm: $(npm -v)${NC}"

# Install dependencies
if [ ! -d "node_modules" ]; then
    echo -e "${CYAN}📦 Installing Node dependencies...${NC}"
    npm install
fi

# Compile TypeScript
echo -e "${CYAN}🔨 Compiling TypeScript...${NC}"
npm run compile

# Package extension
echo -e "${CYAN}📦 Packaging extension...${NC}"

if ! command -v vsce &> /dev/null; then
    echo -e "${YELLOW}Installing vsce...${NC}"
    npm install -g vsce
fi

vsce package --allow-missing-repository

VSIX_FILE=$(ls github-issue-search-*.vsix 2>/dev/null | head -n1)

if [ ! -f "$VSIX_FILE" ]; then
    echo -e "${RED}❌ Failed to package extension${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Extension packaged: $VSIX_FILE${NC}"

# Install extension
echo -e "${CYAN}📥 Installing extension...${NC}"

if command -v code-server &> /dev/null; then
    echo -e "${YELLOW}🔧 Detected code-server environment${NC}"
    code-server --install-extension "$VSIX_FILE" --force
else
    code --install-extension "$VSIX_FILE" --force
fi

# Show usage instructions
echo ""
echo -e "${CYAN}🚀 Usage Instructions:${NC}"
echo "1. Open Command Palette (Ctrl+Shift+P / Cmd+Shift+P)"
echo "2. Search for: 'Search GitHub Issues'"
echo "3. Enter repository (e.g., makeplane/plane)"
echo "4. Enter search keywords"
echo ""
echo -e "${YELLOW}⚙️  Optional Configuration:${NC}"
echo "• Add GitHub token in Settings for higher rate limits"
echo "• Set default repository in Settings"
echo ""
echo -e "${GREEN}🎉 Ready to search! Use Ctrl+Shift+P → 'Search GitHub Issues'${NC}"