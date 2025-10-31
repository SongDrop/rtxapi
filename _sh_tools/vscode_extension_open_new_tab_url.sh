#!/bin/bash

# ===============================================
# VS Code Server "Open Folder in New Tab" Extension Generator
# ===============================================

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║      VS Code Server - Open Folder in New Tab Generator        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Ask for extension details
read -p "Enter extension name (default: vscode-server-open-new-tab): " EXTNAME
EXTNAME=${EXTNAME:-vscode-server-open-new-tab}

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

read -p "Enter display name (default: Open Folder in New Browser Tab): " DISPLAYNAME
DISPLAYNAME=${DISPLAYNAME:-Open Folder in New Browser Tab}

read -p "Enter description (default: Open folders in new browser tabs in VS Code Server): " DESCRIPTION
DESCRIPTION=${DESCRIPTION:-Open folders in new browser tabs in VS Code Server}

read -p "Enter publisher (default: songdropltd): " PUBLISHER
PUBLISHER=${PUBLISHER:-songdropltd}

read -p "Enter repository URL (default: https://github.com/SongDrop/vscode_server_open_new_tab): " REPO
REPO=${REPO:-https://github.com/SongDrop/vscode_server_open_new_tab}

# Create folder structure
echo -e "${CYAN}📁 Creating folder structure...${NC}"
mkdir -p "$EXTNAME/src" "$EXTNAME/media" "$EXTNAME/out"
cd "$EXTNAME" || exit

# Download logo.png
echo -e "${CYAN}🎨 Downloading logo...${NC}"
curl -s "https://i.postimg.cc/tTRcGrkG/logo.png" -o media/logo.png

# Create package.json
echo -e "${CYAN}📦 Creating package.json...${NC}"
cat <<EOL > package.json
{
  "name": "$EXTNAME",
  "displayName": "$DISPLAYNAME",
  "description": "$DESCRIPTION",
  "repository": "$REPO",
  "publisher": "$PUBLISHER",
  "icon": "media/logo.png",
  "version": "1.0.0",
  "engines": {
    "vscode": "^1.96.0"
  },
  "categories": [
    "Other"
  ],
  "activationEvents": [
    "onCommand:$EXTNAME.openFolderNewTab"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {
        "command": "$EXTNAME.openFolderNewTab",
        "title": "Open in New Browser Tab",
        "category": "Folder"
      }
    ],
    "menus": {
      "explorer/context": [
        {
          "command": "$EXTNAME.openFolderNewTab",
          "group": "navigation",
          "when": "explorerResourceIsFolder"
        }
      ]
    },
    "configuration": {
      "title": "Open Folder in New Tab",
      "properties": {
        "$EXTNAME.baseUrl": {
          "type": "string",
          "default": "",
          "description": "Base URL of your VS Code Server (e.g., https://vscode.example.com)"
        }
      }
    }
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./",
    "pretest": "npm run compile && npm run lint",
    "lint": "eslint src",
    "test": "vscode-test"
  },
  "devDependencies": {
    "@types/mocha": "^10.0.10",
    "@types/node": "20.x",
    "@types/vscode": "^1.96.0",
    "@typescript-eslint/eslint-plugin": "^8.17.0",
    "@typescript-eslint/parser": "^8.17.0",
    "@vscode/test-cli": "^0.0.10",
    "@vscode/test-electron": "^2.4.1",
    "eslint": "^9.17.0",
    "typescript": "^5.7.2"
  }
}
EOL

# Create tsconfig.json
echo -e "${CYAN}⚙️ Creating tsconfig.json...${NC}"
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
  },
  "exclude": ["node_modules", ".vscode-test"]
}
EOL

# Create extension.ts
echo -e "${CYAN}🔧 Creating extension source code...${NC}"
# Create extension.ts
echo -e "${CYAN}🔧 Creating extension source code...${NC}"
cat <<'EOL' > src/extension.ts
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
    let disposable = vscode.commands.registerCommand('vscode-server-open-new-tab.openFolderNewTab', async (uri: vscode.Uri) => {
        if (!uri) {
            vscode.window.showErrorMessage('No folder selected');
            return;
        }

        try {
            // Get the folder path
            const folderPath = uri.fsPath;
            
            // Get base URL from configuration or detect current server URL
            const baseUrl = await getBaseUrl();
            
            // Construct the new URL
            const newUrl = `${baseUrl}?folder=${encodeURIComponent(folderPath)}`;
            
            // Open in new browser tab
            await vscode.env.openExternal(vscode.Uri.parse(newUrl));
            
            vscode.window.showInformationMessage(`Opening folder in new tab: ${folderPath}`);
            
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to open folder in new tab: ${error}`);
        }
    });

    context.subscriptions.push(disposable);
}

async function getBaseUrl(): Promise<string> {
    // Try to get from configuration first
    const config = vscode.workspace.getConfiguration('vscode-server-open-new-tab');
    const configuredUrl = config.get('baseUrl') as string;
    
    if (configuredUrl && configuredUrl.trim() !== '') {
        return configuredUrl.trim();
    }
    
    // For VS Code Server, try to get the current workspace to extract base URL
    const workspaceFolders = vscode.workspace.workspaceFolders;
    if (workspaceFolders && workspaceFolders.length > 0) {
        const workspaceUri = workspaceFolders[0].uri;
        
        // If we're in a remote context (like code-server), we can try to construct the URL
        if (workspaceUri.scheme === 'vscode-remote') {
            // Extract host from the remote authority
            const remoteAuthority = workspaceUri.authority;
            // Remove port if present
            const host = remoteAuthority.split(':')[0];
            return `https://${host}`;
        }
    }
    
    // Final fallback - try to use environment variables or prompt user
    const configBaseUrl = process.env.CODE_SERVER_URL || process.env.VSCODE_SERVER_URL;
    if (configBaseUrl) {
        return configBaseUrl;
    }
    
    // Prompt user to configure the setting
    const configure = await vscode.window.showWarningMessage(
        'VS Code Server URL not configured. Please set vscode-server-open-new-tab.baseUrl in settings.',
        'Open Settings',
        'Use Default (localhost)'
    );
    
    if (configure === 'Open Settings') {
        vscode.commands.executeCommand('workbench.action.openSettings', 'vscode-server-open-new-tab.baseUrl');
    } else if (configure === 'Use Default (localhost)') {
        return 'http://localhost:8080';
    }
    
    throw new Error('VS Code Server base URL not configured. Please set vscode-server-open-new-tab.baseUrl in settings.');
}

export function deactivate() {}
EOL


# Create README.md
echo -e "${CYAN}📖 Creating README.md...${NC}"
cat <<EOL > README.md
# $DISPLAYNAME

$DESCRIPTION

## Features

- Right-click any folder in VS Code Explorer and select "Open in New Browser Tab"
- Opens the folder in a new browser tab using your VS Code Server instance
- Configurable base URL for custom VS Code Server deployments

## Installation

1. Build the extension:
\`\`\`bash
npm install
npm run compile
\`\`\`

2. Package and install:
\`\`\`bash
npm install -g vsce
vsce package
code --install-extension $EXTNAME-1.0.0.vsix
\`\`\`

## Configuration

Set your VS Code Server base URL in VS Code settings:
- \`$EXTNAME.baseUrl\`: Base URL of your VS Code Server (e.g., https://vscode.win10dev.xyz)

## Usage

1. Open VS Code with the extension installed
2. Navigate to the Explorer panel
3. Right-click on any folder
4. Select "Open in New Browser Tab"
5. The folder will open in a new browser tab

## Development

\`\`\`bash
# Compile TypeScript
npm run compile

# Watch for changes
npm run watch

# Run tests
npm test

# Package extension
vsce package
\`\`\`
EOL

# Create .vscodeignore
echo -e "${CYAN}📋 Creating .vscodeignore...${NC}"
cat <<EOL > .vscodeignore
.vscode/**
src/**
.gitignore
**/*.map
**/*.ts
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

echo -e "${GREEN}✅ Open Folder in New Tab extension installed successfully!${NC}"


echo "# --- Final instructions ---"
echo "## Configuration"
echo ""
echo "Set your VS Code Server base URL in VS Code settings:"
echo "- \`$EXTNAME.baseUrl\`: Base URL of your VS Code Server (e.g., https://vscode.example.com)"
echo ""
echo "## Usage"
echo ""
echo "1. Open VS Code with the extension installed"
echo "2. Navigate to the Explorer panel"
echo "3. Right-click on any folder"
echo "4. Select \"Open in New Browser Tab\""
echo "5. The folder will open in a new browser tab"