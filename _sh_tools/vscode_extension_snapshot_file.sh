#!/bin/bash

# ===============================================
# Snapshot File VS Code Extension 
# ===============================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🚀 Installing Snapshot File VS Code Extension...${NC}"


# Ask for extension name
read -p "Enter your Python snapshot extension folder name (default: vscode_snapshot): " EXTNAME
EXTNAME=${EXTNAME:-vscode_snapshot}

# Check if folder exists
if [ -d "$EXTNAME" ]; then
    read -p "Folder '$EXTNAME' already exists. Do you want to remove it? (y/N): " REMOVE
    REMOVE=${REMOVE:-N}
    if [[ "$REMOVE" == "y" || "$REMOVE" == "Y" ]]; then
        echo "Removing existing folder '$EXTNAME'..."
        rm -rf "$EXTNAME"
    else
        echo "Exiting to avoid overwriting existing folder."
        exit 1
    fi
fi

# Create folder structure
mkdir -p "$EXTNAME/src" "$EXTNAME/media" "$EXTNAME/scripts" "$EXTNAME/snapshots"
cd "$EXTNAME" || exit

# Download logo
echo -e "${CYAN}📥 Downloading Snapshot logo...${NC}"
curl -s -o media/logo.png "https://i.postimg.cc/HssSGkwj/logo.png"


# Create package.json
cat <<EOL > package.json
{
  "name": "$EXTNAME",
  "displayName": "$EXTNAME",
  "publisher": "songdropltd",
  "description": "VS Code extension to snapshot Python/HTML files",
  "icon": "media/logo.png",
  "version": "0.0.1",
  "engines": { "vscode": "^1.81.0" },
  "activationEvents": ["onView:snapshotView"],
  "main": "./out/extension.js",
  "scripts": {
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./"
  },
  "devDependencies": {
    "typescript": "^5.9.2",
    "@types/node": "^20.6.2",
    "@types/vscode": "^1.81.0"
  },
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "snapshotActivity",
          "title": "Snapshots",
          "icon": "media/logo.png"
        }
      ]
    },
    "views": {
      "snapshotActivity": [
        {
          "id": "snapshotView",
          "name": "Snapshot Sidebar",
          "type": "webview",
          "icon": "media/logo.png"
        }
      ]
    }
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
    "lib": ["ES2020", "DOM"],
    "sourceMap": true,
    "rootDir": "src",
    "strict": true,
    "types": ["node"] // 👈 add this, VERY IMPORTANT!
  },
  "exclude": ["node_modules", ".vscode-test"]
}
EOL

# Create src/extension.ts
cat <<EOL > src/extension.ts
import * as vscode from "vscode";
import { SnapshotPanel } from "./webview";

export function activate(context: vscode.ExtensionContext) {
    const provider = new SnapshotPanel(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("snapshotView", provider)
    );
}

export function deactivate() {}
EOL

# Create src/generate_html.ts
cat <<'EOL' > src/generate_html.ts
export function generateHtml(nonce: string, cspSource: string): string {
  return `
   <!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <title>Snapshot</title>
  <style>
    body { 
      font-family: sans-serif; 
      padding: 16px; 
      background: var(--vscode-sideBar-background);
      color: white;
    }
    button { 
      padding: 8px 12px; 
      font-size: 13px; 
      cursor: pointer; 
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      border-radius: 3px;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    .loader {
      display: none;
      width: 20px;
      height: 20px;
      border: 2px solid white;
      border-top: 2px solid transparent;
      border-radius: 50%;
      animation: spin 1s linear infinite;
      margin: 8px auto;
    }
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
    .status {
      margin: 8px 0;
      font-size: 12px;
      min-height: 16px;
    }
    .success { color: var(--vscode-testing-iconPassed); }
    .error { color: var(--vscode-testing-iconFailed); }
    .folder-link {
      display: none;
      margin-top: 8px;
      font-size: 12px;
    }
    .folder-link a {
      color: var(--vscode-textLink-foreground);
      text-decoration: none;
    }
    .folder-link a:hover {
      text-decoration: underline;
    }
  </style>
</head>
<body>
  <h3 style="margin: 0px">
  <svg class="svg-icon" style="width: 1em; height: 1em;vertical-align: middle;fill: currentColor;overflow: hidden;" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg"><path d="M377.0079763 162.6041205H245.61234173c-45.82665482 0-83.10935703 37.02379457-83.10935704 82.72099555v131.78399605c0 11.9097521 9.5795832 21.48933531 21.48933531 21.48933531 11.9097521 0 21.48933531-9.5795832 21.48933531-21.48933531V245.19566222c0-21.8776968 17.99408197-39.61287111 40.0012326-39.61287111h131.26618073c11.9097521 0 21.48933531-9.5795832 21.48933531-21.4893353 0.25890765-11.9097521-9.32067555-21.48933531-21.23042765-21.48933531zM377.0079763 795.89224297H245.61234173c-22.13660445 0-40.00123259-17.73517431-40.00123259-39.61287112V624.49537581c0-11.9097521-9.5795832-21.48933531-21.48933531-21.48933531-11.9097521 0-21.48933531 9.5795832-21.4893353 21.48933531v131.78399604c0 45.56774717 37.28270222 82.72099555 83.10935703 82.72099556h131.26618074c11.9097521 0 21.48933531-9.5795832 21.48933532-21.48933531s-9.5795832-21.61878914-21.48933532-21.61878913zM756.30768988 162.6041205H624.52369383c-11.9097521 0-21.48933531 9.5795832-21.4893353 21.48933531 0 11.9097521 9.5795832 21.48933531 21.4893353 21.4893353h131.78399605c21.8776968 0 39.61287111 17.73517431 39.6128711 39.61287111v131.78399605c0 11.9097521 9.5795832 21.48933531 21.48933532 21.48933531 11.9097521 0 21.48933531-9.5795832 21.48933532-21.48933531V245.19566222c0.12945383-45.56774717-37.02379457-82.59154173-82.59154174-82.59154172zM817.4098963 603.0060405c-11.9097521 0-21.48933531 9.5795832-21.48933532 21.48933531v131.78399604c0 21.8776968-17.73517431 39.61287111-39.6128711 39.61287112H624.52369383c-11.9097521 0-21.48933531 9.5795832-21.4893353 21.4893353s9.5795832 21.48933531 21.4893353 21.48933531h131.78399605c45.56774717 0 82.72099555-37.02379457 82.72099555-82.72099555V624.49537581c0-11.9097521-9.70903703-21.48933531-21.61878913-21.48933531z" fill="#FF2C2C" /><path d="M500.76583506 517.04869925m-68.09271309 0a68.09271309 68.09271309 0 1 0 136.18542618 0 68.09271309 68.09271309 0 1 0-136.18542618 0Z" fill="#FF2C2C" /><path d="M657.92278125 385.78251852h-53.3349768c-8.15559111 0-15.53445925-3.88361482-19.80643555-10.74466766l-12.42756742-17.60572049c-4.2719763-6.47269136-11.65084445-10.35630617-19.41807407-10.35630618h-109.38848394c-7.76722963 0-15.01664395 3.88361482-19.80643556 10.35630618l-12.03920594 17.60572049c-4.78979161 6.86105283-12.03920592 10.74466765-19.80643555 10.74466766h-47.76846222c-19.41807408 0-35.34089482 15.53445925-35.34089481 34.82307951v198.97053234c0 19.41807408 15.92282075 34.8230795 35.34089481 34.8230795h313.92553086c19.41807408 0 34.8230795-15.53445925 34.82307952-34.8230795V420.60559803c-0.12945383-19.28862025-15.53445925-34.8230795-34.95253333-34.82307951z m-157.15694619 227.83873579c-52.94661531 0-96.44310124-43.10812445-96.44310123-96.44310122s43.49648592-96.44310124 96.44310123-96.44310124c53.3349768 0 96.83146272 43.10812445 96.83146272 96.44310124s-43.49648592 96.44310124-96.83146272 96.44310122z" fill="#FFFFFF" /></svg>
  File Snapshot</h3>
  
  <button id="snapshot" style="margin-top: 6px;">Snapshot Active File</button>
  <div class="loader" id="loader"></div>
  
  <div class="status" id="status"></div>
  
  <div class="folder-link" id="folderLink">
    <a href="#" id="openFolder">📁 Open snapshots folder</a>
  </div>
  
  <p style="font-size: 12px; margin-top: 16px; color: var(--vscode-descriptionForeground);">
    Converts files to PNG in your snapshots folder.<br>
    Wait for the popup confirmation.
  </p>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const snapshotBtn = document.getElementById('snapshot');
    const loader = document.getElementById('loader');
    const status = document.getElementById('status');
    const folderLink = document.getElementById('folderLink');
    const openFolder = document.getElementById('openFolder');

    snapshotBtn.addEventListener('click', () => {
      // Show loading state
      snapshotBtn.disabled = true;
      loader.style.display = 'block';
      status.textContent = 'Creating snapshot...';
      status.className = 'status';
      folderLink.style.display = 'none';
      
      vscode.postMessage({ 
        command: 'snapshot',
        timestamp: Date.now()
      });
    });

    openFolder.addEventListener('click', (e) => {
      e.preventDefault();
      vscode.postMessage({ 
        command: 'openFolder'
      });
    });

    // Handle messages from extension
    window.addEventListener('message', event => {
      const message = event.data;
      
      switch (message.command) {
        case 'snapshotStarted':
          snapshotBtn.disabled = true;
          loader.style.display = 'block';
          status.textContent = 'Creating snapshot...';
          status.className = 'status';
          break;
          
        case 'snapshotSuccess':
          snapshotBtn.disabled = false;
          loader.style.display = 'none';
          status.textContent = '✅ Snapshot created successfully!';
          status.className = 'status success';
          folderLink.style.display = 'block';
          break;
          
        case 'snapshotError':
          snapshotBtn.disabled = false;
          loader.style.display = 'none';
          status.textContent = '❌ ' + message.error;
          status.className = 'status error';
          folderLink.style.display = 'none';
          break;
      }
    });
  </script>
</body>
</html>
  `;
}
EOL


# Create src/webview.ts
cat <<'EOL' > src/webview.ts
import * as vscode from "vscode";
import * as path from "path";
import { exec } from "child_process";
import { platform } from "os";
import { generateHtml } from "./generate_html";

export class SnapshotPanel implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;

    constructor(private readonly context: vscode.ExtensionContext) {}

    // Update the resolveWebviewView method in webview.ts
    resolveWebviewView(webviewView: vscode.WebviewView, _context: vscode.WebviewViewResolveContext, _token: vscode.CancellationToken) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };

        const nonce = this.getNonce();
        const cspSource = webviewView.webview.cspSource;
        webviewView.webview.html = generateHtml(nonce, cspSource);

        webviewView.webview.onDidReceiveMessage(async message => {
            switch (message.command) {
                case 'snapshot':
                    await this.snapshotActiveFile();
                    break;
                case 'openFolder':
                    await this.openSnapshotsFolder();
                    break;
            }
        });
    }

    private async snapshotActiveFile() {
        // Notify webview that snapshot started
        this._view?.webview.postMessage({ command: 'snapshotStarted' });

        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            const error = "No active file to snapshot!";
            this._view?.webview.postMessage({ command: 'snapshotError', error });
            vscode.window.showErrorMessage(error);
            return;
        }

        const filePath = editor.document.fileName;
        const ext = filePath.split('.').pop()?.toLowerCase();

        let script = "";
        switch (ext) {
            case "py":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_python.py");
                break;
            case "html":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_html.py");
                break;
            case "sh":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_sh.py");
                break;
            case "yml":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_yml.py");
                break;
            case "c":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_c.py");
                break;
            case "cpp":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_cpp.py");
                break;
            case "lua":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_lua.py");
                break;
            case "uc":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_uc.py");
                break;
            case "cfg":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_cfg.py");
                break;
            case "txt":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_txt.py");
                break;
            case "md":
                script = path.join(this.context.extensionPath, "scripts", "snapshot_md.py");
                break;
            default:
                const error = "Snapshot not supported for this file type.";
                this._view?.webview.postMessage({ command: 'snapshotError', error });
                vscode.window.showErrorMessage(error);
                return;
        }

        try {
            // Path to Python in your virtual environment
            const envPath = path.join(this.context.extensionPath, "myenv");
            const pythonCmd =
                platform() === "win32"
                    ? path.join(envPath, "Scripts", "python.exe")
                    : path.join(envPath, "bin", "python3");

            // Get workspace folder (VS Code project root)
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";

            // Pass workspace folder as environment variable
            const env = { ...process.env, VSCODE_WORKSPACE: workspaceFolder };

            // Execute the Python script
            await new Promise<void>((resolve, reject) => {
                exec(`${pythonCmd} "${script}" "${filePath}"`, { env }, (err, stdout, stderr) => {
                    if (err) {
                        reject(stderr || err.message);
                    } else {
                        // Notify webview of success
                        this._view?.webview.postMessage({ command: 'snapshotSuccess' });
                        vscode.window.showInformationMessage(stdout);
                        resolve();
                    }
                });
            });

        } catch (error) {
            const errorMsg = `Error: ${error}`;
            this._view?.webview.postMessage({ command: 'snapshotError', error: errorMsg });
            vscode.window.showErrorMessage(errorMsg);
        }
    }

    private async openSnapshotsFolder() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || "";
        const workspaceEnv = workspaceFolder || "";
        
        let snapshotsDir: string;
        
        if (workspaceEnv && await this.dirExists(workspaceEnv)) {
            snapshotsDir = path.join(workspaceEnv, "snapshots");
        } else {
            snapshotsDir = path.join(require('os').homedir(), "vscode_snapshots", "snapshots");
        }

        // Create directory if it doesn't exist
        if (!await this.dirExists(snapshotsDir)) {
            require('fs').mkdirSync(snapshotsDir, { recursive: true });
        }

        // Open in system file explorer (doesn't affect VS Code workspace)
        vscode.env.openExternal(vscode.Uri.file(snapshotsDir));
    }

    private async dirExists(path: string): Promise<boolean> {
        try {
            const stats = await require('fs').promises.stat(path);
            return stats.isDirectory();
        } catch {
            return false;
        }
    }

    private getNonce(): string {
        return Math.random().toString(36).substring(2, 15);
    }
}
EOL


# Create snapshot_python.py
cat <<'EOL' > scripts/snapshot_python.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, PythonLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_python.py <filename.py>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL


# Create snapshot_html.py
cat <<'EOL' > scripts/snapshot_html.py
import sys
import os
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_html(input_html: str):
    output_dir = get_safe_output_dir()
    output_file = output_dir / (Path(input_html).stem + ".png")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"file://{Path(input_html).resolve()}")
        page.screenshot(path=str(output_file), full_page=True)
        browser.close()

    print(f"✅ Saved snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_html.py <filename.html>")
        sys.exit(1)
    snapshot_html(sys.argv[1])
EOL

# Create snapshot_sh.py
cat <<'EOL' > scripts/snapshot_sh.py
# scripts/snapshot_sh.py
import sys
import os
import tempfile
from pathlib import Path
from pygments import highlight
from pygments.lexers import BashLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_sh(input_sh: str):
    output_dir = get_safe_output_dir()
    output_file = output_dir / (Path(input_sh).stem + ".png")

    code = Path(input_sh).read_text(encoding="utf-8")

    # Use ImageFormatter for clean light-mode syntax highlighting with line numbers
    formatter = ImageFormatter(
        font_name="Menlo",             # Monospace font
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f9f9f9",      # Light background for line numbers
        line_number_fg="#888888",
        style="friendly",              # Light Pygments theme
        font_size=22,
        line_number_separator=True,
        line_number_chars=4,
        hl_color="#ffffcc",            # Highlight color (soft yellow)
        dpi=220,                       # Higher DPI for sharper text
        bgcolor="#ffffff"              # Light mode background
    )

    img_data = highlight(code, BashLexer(), formatter)

    with open(output_file, "wb") as f:
        f.write(img_data)

    print(f"✅ Saved Bash snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_sh.py <script.sh>")
        sys.exit(1)
    snapshot_sh(sys.argv[1])
EOL

# Create snapshot_yml.py
cat <<'EOL' > scripts/snapshot_yml.py
import sys
import os
import tempfile
from pathlib import Path
from pygments import highlight
from pygments.lexers import YamlLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_yml(input_yml: str):
    output_dir = get_safe_output_dir()
    output_file = output_dir / (Path(input_yml).stem + ".png")

    code = Path(input_yml).read_text(encoding="utf-8")

    # Use ImageFormatter for clean light-mode syntax highlighting with line numbers
    formatter = ImageFormatter(
        font_name="Menlo",             # Monospace font
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f9f9f9",      # Light background for line numbers
        line_number_fg="#888888",
        style="friendly",              # Light Pygments theme
        font_size=22,
        line_number_separator=True,
        line_number_chars=4,
        hl_color="#ffffcc",            # Highlight color (soft yellow)
        dpi=220,                       # Higher DPI for sharper text
        bgcolor="#ffffff"              # Light mode background
    )

    img_data = highlight(code, YamlLexer(), formatter)

    with open(output_file, "wb") as f:
        f.write(img_data)

    print(f"✅ Saved YML snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_yml.py <filename.yml>")
        sys.exit(1)
    snapshot_yml(sys.argv[1])
EOL

# Create snapshot_c.py
cat <<'EOL' > scripts/snapshot_c.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, CLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved C snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_c.py <filename.c>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL

# Create snapshot_cpp.py
cat <<'EOL' > scripts/snapshot_cpp.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import CppLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, CppLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved C++ snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_cpp.py <filename.cpp>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL

# Create snapshot_lua.py
cat <<'EOL' > scripts/snapshot_lua.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import LuaLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, LuaLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved Lua snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_lua.py <filename.lua>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL

# Create snapshot_uc.py
cat <<'EOL' > scripts/snapshot_uc.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import CppLexer  # UnrealScript is similar to C++
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, CppLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved UnrealScript snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_uc.py <filename.uc>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL

cat <<'EOL' > scripts/snapshot_txt.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import TextLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, TextLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved TXT snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_txt.py <filename.txt>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL

cat <<'EOL' > scripts/snapshot_cfg.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import IniLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, IniLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved CFG snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_cfg.py <filename.cfg>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL


cat <<'EOL' > scripts/snapshot_md.py
import sys
from pathlib import Path
import os
import tempfile
from pygments import highlight
from pygments.lexers import MarkdownLexer
from pygments.formatters import ImageFormatter

def get_safe_output_dir():
    workspace_env = os.environ.get("VSCODE_WORKSPACE", "").strip()
    if workspace_env and os.path.isdir(workspace_env):
        workspace = Path(workspace_env)
    else:
        home_dir = Path.home() / "vscode_snapshots"
        if os.access(home_dir, os.W_OK) or not home_dir.exists():
            workspace = home_dir
        else:
            workspace = Path(tempfile.gettempdir()) / "vscode_snapshots"
    output_dir = workspace / "snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def snapshot_code(input_file: str):
    output_dir = get_safe_output_dir()
    code = Path(input_file).read_text(encoding="utf-8")

    formatter = ImageFormatter(
        font_name="Menlo",
        line_numbers=True,
        line_number_pad=32,
        image_pad=20,
        line_number_bg="#f0f0f0",
        line_number_fg="#888888",
        style="default",
        font_size=24,
        bgcolor=None
    )

    img_data = highlight(code, MarkdownLexer(), formatter)
    output_file = output_dir / (Path(input_file).stem + ".png")

    with open(output_file, "wb") as f:
        f.write(img_data)
    print(f"✅ Saved MD snapshot: {output_file.resolve()}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python snapshot_md.py <filename.md>")
        sys.exit(1)
    snapshot_code(sys.argv[1])
EOL


# Create requirements.txt
cat <<EOL > requirements.txt
pygments
pillow
playwright
cairosvg
EOL

# Create README.md
cat <<EOL > README.md
# $EXTNAME VS Code Extension

## Setup

1. Install Python dependencies:
\`\`\`bash
pip install -r requirements.txt
\`\`\`

2. Install Node dependencies and compile:
\`\`\`bash
npm install
npm run compile
\`\`\`

3. Open VS Code → Sidebar → Snapshots → click "Snapshot Active File".

Snapshots are saved in \`snapshots/<filename>.png\`.
EOL

echo "✅ Python snapshot VS Code extension scaffold created in '$EXTNAME'."

# -----------------------------
# Create .vscodeignore to exclude unnecessary files
# -----------------------------
cat <<EOL > .vscodeignore
node_modules
.vscode
*.ts
*.map
.git
.gitignore
EOL

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

# -----------------------------
# Python Environment & Dependencies
# -----------------------------

# Create and activate Python virtual environment
python3.10 -m venv myenv
source myenv/bin/activate

# Upgrade pip and install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright browsers (needed for HTML and YML snapshots)
echo "Installing Playwright browsers..."
python -m playwright install chromium


# Package extension
echo -e "${CYAN}📦 Packaging extension...${NC}"

if ! command -v vsce &> /dev/null; then
    echo -e "${YELLOW}Installing vsce...${NC}"
    npm install -g vsce
fi

vsce package --allow-missing-repository

VSIX_FILE=$(ls bytestash-*.vsix 2>/dev/null | head -n1)

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

echo -e "${GREEN}✅ ByteStash extension installed successfully!${NC}"
