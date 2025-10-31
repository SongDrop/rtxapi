#!/bin/bash
set -e

# ===============================================
# ByteStash VS Code Extension 
# ===============================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🚀 Installing ByteStash VS Code Extension...${NC}"

# Ask for extension name
read -p "Enter your extension folder name (default: vscode_bytestash): " EXTNAME
EXTNAME=${EXTNAME:-vscode_bytestash}

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

# Create folder structure
mkdir -p "$EXTNAME/src" "$EXTNAME/media" "$EXTNAME/out"
cd "$EXTNAME" || exit

# Download logo
echo -e "${CYAN}📥 Downloading Bytestash logo...${NC}"
curl -s -o media/logo.png "https://i.postimg.cc/FFb5ZzZZ/logo.png"

# Create a fixed package.json with proper activation events
cat <<EOL > package.json
{
  "name": "bytestash",
  "displayName": "ByteStash",
  "description": "Upload snippets to ByteStash from VS Code",
  "repository": "https://github.com/SongDrop/ByteStash",
  "publisher": "songdropltd",
  "icon": "media/logo.png",
  "version": "0.0.6",
  "engines": {
    "vscode": "^1.96.0"
  },
  "categories": [
    "Other"
  ],
  "activationEvents": [],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {
        "command": "bytestash.pushAll",
        "category": "ByteStash",
        "title": "Push to ByteStash"
      },
      {
        "command": "bytestash.pushSelected",
        "category": "ByteStash",
        "title": "Push Selected to ByteStash"
      }
    ],
    "menus": {
      "explorer/context": [
        {
          "command": "bytestash.pushAll",
          "group": "navigation"
        }
      ],
      "editor/context": [
        {
          "command": "bytestash.pushSelected",
          "group": "navigation"
        }
      ],
      "editor/title": [
        {
          "command": "bytestash.pushAll",
          "group": "navigation"
        }
      ]
    },
    "configuration": {
      "title": "ByteStash",
      "properties": {
        "bytestash.url": {
          "type": "string",
          "default": "http://localhost:5000",
          "description": "URL of your ByteStash instance"
        },
        "bytestash.key": {
          "type": "string",
          "description": "API key of your Bytestash instance"
        },
        "bytestash.quick": {
          "type": "boolean",
          "description": "Upload directly without asking for input"
        },
        "bytestash.filenameAsTitle": {
          "type": "boolean",
          "description": "Use file name as title instead of a random string"
        },
        "bytestash.public": {
          "type": "boolean",
          "description": "Make uploaded snippets public"
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
  },
  "dependencies": {
    "typescript-eslint": "^8.19.0"
  }
}
EOL

# Create tsconfig.json
cat <<EOL > tsconfig.json
{
	"compilerOptions": {
		"module": "Node16",
		"target": "ES2022",
		"outDir": "out",
		"lib": [
			"ES2022"
		],
		"sourceMap": true,
		"rootDir": "src",
		"strict": true,   /* enable all strict type-checking options */
		/* Additional Checks */
		// "noImplicitReturns": true, /* Report error when not all code paths in function return a value. */
		// "noFallthroughCasesInSwitch": true, /* Report errors for fallthrough cases in switch statement. */
		// "noUnusedParameters": true,  /* Report errors on unused parameters. */
	}
}
EOL

# Create extension.ts
cat <<'EOL' > src/extension.ts
import { readFileSync } from "fs";
import * as vscode from "vscode";

async function pushSnippet(
  content: string | undefined,
  file: string | undefined,
  language: string
) {
  // Languages available in ByteStash, use plaintext if unavailable
  const available_languages = [
    "javascript",
    "typescript",
    "html",
    "css",
    "php",
    "wat",
    "c",
    "cpp",
    "csharp",
    "rust",
    "go",
    "java",
    "kotlin",
    "scala",
    "groovy",
    "python",
    "ruby",
    "perl",
    "lua",
    "bash",
    "powershell",
    "bat",
    "sql",
    "mongodb",
    "markdown",
    "yaml",
    "json",
    "xml",
    "toml",
    "terraform",
    "dockerfile",
    "kubernetes",
    "swift",
    "r",
    "julia",
    "dart",
    "elm",
    "apex",
    "solidity",
    "vyper",
    "latex",
    "matlab",
    "graphql",
    "cypher",
    "plaintext",
  ];

  const config = vscode.workspace.getConfiguration("bytestash");
  const config_url = config.url;
  const config_key = config.key;
  const config_quick = config.quick;
  const config_fileNameAsTitle = config.filenameAsTitle;
  const config_public = config.public;

  // Enhanced config validation with open settings options
  if (config_url === null || config_url === undefined) {
    const action = await vscode.window.showErrorMessage(
      "ByteStash URL was not configured!",
      "Open Settings",
      "Cancel"
    );
    if (action === "Open Settings") {
      vscode.commands.executeCommand("workbench.action.openSettings", "bytestash.url");
    }
    return;
  }

  if (config_key === null || config_key === undefined) {
    const action = await vscode.window.showErrorMessage(
      "ByteStash API key was not configured!",
      "Open Settings",
      "Cancel"
    );
    if (action === "Open Settings") {
      vscode.commands.executeCommand("workbench.action.openSettings", "bytestash.key");
    }
    return;
  }

  if (content === null || content === undefined || content === "") {
    vscode.window.showInformationMessage(
      "Unable to find any content to upload!"
    );
    return;
  }

  const default_name =
    file === "" || !config_fileNameAsTitle ? crypto.randomUUID() : file;
  const default_description = "Uploaded from VS Code";
  const default_category = "vscode";
  // Ask for name
  const name = config_quick
    ? default_name
    : await vscode.window.showInputBox({
        prompt: "Enter a name:",
        value: default_name,
      });

  // Ask for a description
  const description = config_quick
    ? default_description
    : await vscode.window.showInputBox({
        prompt: "Enter a description:",
        value: default_description,
      });

  // Ask for a category
  const category = config_quick
    ? default_category
    : await vscode.window.showInputBox({
        prompt: "Enter a category:",
        value: default_category,
      });

  // Compose fragments
  const fragments = [
    {
      file_name: file,
      code: content,
      language: available_languages.includes(language) ? language : "plaintext",
    },
  ];

  const fragments_json = JSON.stringify(fragments);

  // Compose body
  const body = {
    title: name,
    description: description,
    categories: category,
    is_public: config_public.toString(),
    fragments: fragments_json,
  };

  const body_json = JSON.stringify(body);

  const response = await fetch(`${config_url}/api/v1/snippets/push`, {
    method: "POST",
    body: body_json,
    headers: { "Content-Type": "application/json", "x-api-key": config_key },
  });

  if (response.ok) {
    vscode.window.showInformationMessage(`Snippet uploaded successfully!`);
  } else {
    response.text().then(function (text) {
      vscode.window.showInformationMessage(text);
    });
  }
}

function getDocument() {
  const editor = vscode.window.activeTextEditor;

  if (editor) {
    return editor.document;
  }

  return undefined;
}

function getSelection() {
  const editor = vscode.window.activeTextEditor;

  if (editor) {
    return editor.selection;
  }

  return undefined;
}

function getContent() {
  const document = getDocument();

  if (document) {
    return document.getText();
  }

  return undefined;
}

function getFileContent(resource: vscode.Uri) {
  return Buffer.from(readFileSync(resource.path)).toString();
}

function extractFileName(file: string) {
  const nameArray = file.split("/");
  return nameArray[nameArray.length - 1];
}

function getFileName() {
  const document = getDocument();

  if (document) {
    return extractFileName(document.fileName);
  }

  return undefined;
}

function getFileLanguage() {
  const document = getDocument();

  if (document) {
    return document.languageId;
  }

  return "plaintext";
}

function getSelectionContent() {
  const document = getDocument();
  const selection = getSelection();

  if (document && selection) {
    return document.getText(selection);
  }

  return undefined;
}

export function activate(context: vscode.ExtensionContext) {
  const disposable_all = vscode.commands.registerCommand(
    "bytestash.pushAll",
    async (resource: vscode.Uri) => {
      // Quick config check before proceeding
      const config = vscode.workspace.getConfiguration("bytestash");
      const config_url = config.url;
      const config_key = config.key;

      // If any required config is missing, show settings prompt
      if (!config_url || !config_key) {
        const action = await vscode.window.showWarningMessage(
          'ByteStash configuration incomplete. Please configure your ByteStash URL and API key.',
          'Open Settings',
          'Cancel'
        );
        
        if (action === 'Open Settings') {
          vscode.commands.executeCommand('workbench.action.openSettings', 'bytestash');
          return;
        }
        return;
      }

      if (resource) {
        vscode.workspace.openTextDocument(resource).then((document) => {
          pushSnippet(
            getFileContent(resource),
            extractFileName(resource.path),
            document.languageId
          );
        });
      } else {
        pushSnippet(getContent(), getFileName(), getFileLanguage());
      }
    }
  );

  const disposable_selection = vscode.commands.registerCommand(
    "bytestash.pushSelected",
    async () => {
      // Quick config check before proceeding
      const config = vscode.workspace.getConfiguration("bytestash");
      const config_url = config.url;
      const config_key = config.key;

      // If any required config is missing, show settings prompt
      if (!config_url || !config_key) {
        const action = await vscode.window.showWarningMessage(
          'ByteStash configuration incomplete. Please configure your ByteStash URL and API key.',
          'Open Settings',
          'Cancel'
        );
        
        if (action === 'Open Settings') {
          vscode.commands.executeCommand('workbench.action.openSettings', 'bytestash');
          return;
        }
        return;
      }

      pushSnippet(getSelectionContent(), getFileName(), getFileLanguage());
    }
  );

  context.subscriptions.push(disposable_all);
  context.subscriptions.push(disposable_selection);
}

export function deactivate() {}
EOL

# Create .vscodeignore
cat <<EOL > .vscodeignore
node_modules
.vscode
src
*.ts
*.map
.git
.gitignore
*.sh
EOL

# Create README.md
cat <<EOL > README.md
# bytestash README

This extension allows you to upload snippets to ByteStash directly from VS Code.

Run:

```
chmod +x ./vscode_install.sh
./vscode_install.sh
```

It will automatically install as a vscode extension.
Right click on the file -> Push to Bytestash

In Code > Preferences > Settings
Search for 'Bytestash' to configure API

## Features

### Push

Pushes the content of the current file. Available as a command, from the file context menu and from the editor title bar.

### Push Selected

Pushes the selected content. Available as a command and from the editor context menu.

### Quick Mode

Enabling quick mode creates a new snippet without asking for user input (such as for naming). Title and language will be based on information extracted from VS Code.

## Extension Settings

This extension contributes the following settings:

- `bytestash.url`: URL of your ByteStash instance.
- `bytestash.key`: API key of your ByteStash instance.
- `bytestash.quick`: Upload directly without asking for input.
- `bytestash.filenameAsTitle`: Use file name as title instead of a random string.
- `bytestash.public`: Make uploaded snippets public.

## Known Issues

- None at the moment

## Notes

The ByteStash API is designed in a weird way (such as taking a string instead of a JSON array or taking a string instead of a boolean). This extension is designed to accomodate this but an update might be required if the ByteStash API changes.
EOL

echo -e "${GREEN}✅ Extension scaffold created in '$EXTNAME'${NC}"


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

echo -e "${GREEN}✅ ByteStash extension installed successfully!${NC}"

# --- Final instructions ---
echo ""
echo "🎉 Installation complete!"
echo ""
echo "To use ByteStash extension in VS Code:"
echo "1. Open a workspace in VS Code"
echo "2. Open the Command Palette (Cmd+Shift+P / Ctrl+Shift+P)"
echo "3. Search for 'ByteStash: Push' or 'ByteStash: Push Selected'"
echo "4. Configure extension settings under Preferences → Settings → Extensions → ByteStash"
echo ""
echo -e "${GREEN}🎉 Ready to use! Right-click any HTML file → 'Upload HTML to Spaces'${NC}"