#!/bin/bash
set -e

# ===============================================
# Digital Ocean Spaces Uploader VS Code Extension
# ===============================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🚀 Creating Digital Ocean Spaces Media Uploader Extension...${NC}"

# Ask for extension name
read -p "Enter your extension folder name (default: vscode_dospaces-media-uploader): " EXTNAME
EXTNAME=${EXTNAME:-vscode_dospaces-media-uploader}

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
echo -e "${CYAN}📥 Downloading Digital Ocean logo...${NC}"
curl -s -o media/logo.png "https://i.postimg.cc/yNRV8wdb/DOCN.png"

# Create a fixed package.json with proper activation events
# Create a fixed package.json with proper activation events
cat <<EOL > package.json
{
  "name": "dospaces-media-uploader",
  "displayName": "Digital Ocean Spaces Media Uploader",
  "description": "One-click MEDIA uploader to Digital Ocean Spaces",
  "repository": "https://github.com/SongDrop/dospaces-uploader",
  "publisher": "songdropltd",
  "icon": "media/logo.png",
  "version": "1.0.0",
  "engines": {
    "vscode": "^1.96.0"
  },
  "categories": [
    "Other"
  ],
  "activationEvents": [
    "onFileSystem:file",
    "onCommand:dospaces.uploadMedia"
  ],
  "main": "./out/extension.js",
  "contributes": {
    "commands": [
      {
        "command": "dospaces.uploadMedia",
        "title": "Upload Media to DO Spaces",
        "category": "DigitalOcean"
      }
    ],
    "menus": {
      "explorer/context": [
        {
          "command": "dospaces.uploadMedia",
          "group": "navigation",
          "when": "resourceExtname in ['.jpeg', '.jpg', '.mp4', '.mov', '.png']"
        }
      ],
      "editor/title": [
        {
          "command": "dospaces.uploadMedia",
          "group": "navigation",
          "when": "resourceExtname in ['.jpeg', '.jpg', '.mp4', '.mov', '.png']"
        }
      ]
    },
    "configuration": {
      "title": "Digital Ocean Spaces",
      "properties": {
        "dospaces.accessKey": {
          "type": "string",
          "description": "Digital Ocean Spaces Access Key"
        },
        "dospaces.secretKey": {
          "type": "string",
          "description": "Digital Ocean Spaces Secret Key"
        },
        "dospaces.endpoint": {
          "type": "string",
          "default": "https://nyc3.digitaloceanspaces.com",
          "description": "Spaces Endpoint URL"
        },
        "dospaces.cdnEndpoint": {
          "type": "string",
          "description": "CDN Endpoint URL (optional - if provided, will use this for public URLs instead of Spaces URL)"
        },
        "dospaces.bucket": {
          "type": "string",
          "description": "Spaces Bucket Name"
        },
        "dospaces.region": {
          "type": "string",
          "default": "us-east-1",
          "description": "Spaces Region"
        },
        "dospaces.folder": {
          "type": "string",
          "default": "uploads",
          "description": "Target folder in bucket"
        },
        "dospaces.makePublic": {
          "type": "boolean",
          "default": true,
          "description": "Make uploaded files publicly accessible"
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
    "@types/node": "20.x",
    "@types/vscode": "^1.96.0",
    "typescript": "^5.7.2"
  },
  "dependencies": {
    "@aws-sdk/client-s3": "^3.654.0"
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

export function activate(context: vscode.ExtensionContext) {
    console.log('✅ Digital Ocean Spaces Uploader activated!');
    
    const disposable = vscode.commands.registerCommand("dospaces.uploadMedia", async (resource: vscode.Uri) => {
        if (resource) {
            // Determine content type based on file extension
            const fileExtension = resource.fsPath.split('.').pop()?.toLowerCase();
            let contentType = "application/octet-stream";
            const supportedExtensions = ['jpg', 'jpeg', 'png', 'mp4', 'mov'];     
            if (!supportedExtensions.includes(fileExtension || '')) {
                vscode.window.showWarningMessage("This command only works with media files (JPEG, PNG, MP4, MOV)");
                return;
            }
            
            if (fileExtension === 'jpg' || fileExtension === 'jpeg') {
                contentType = "image/jpeg";
            } else if (fileExtension === 'png') {
                contentType = "image/png";
            } else if (fileExtension === 'mp4') {
                contentType = "video/mp4";
            } else if (fileExtension === 'mov') {
                contentType = "video/quicktime";
            }

            // Use readFileSync for binary files instead of getText()
            const content = readFileSync(resource.fsPath);
            const fileName = resource.fsPath.split('/').pop();
            
            // Test config access first
            const config = vscode.workspace.getConfiguration("dospaces");
            const accessKey = config.get('accessKey') as string;
            const secretKey = config.get('secretKey') as string;
            const bucket = config.get('bucket') as string;
            const endpoint = config.get('endpoint') as string || "https://nyc3.digitaloceanspaces.com";
            const region = config.get('region') as string || "us-east-1";
            const folder = config.get('folder') as string || "uploads";
            const makePublic = config.get('makePublic') as boolean || true;
            
            // Enhanced config validation with open settings options
            if (!accessKey) {
                const action = await vscode.window.showErrorMessage(
                    'Digital Ocean Spaces Access Key not configured!',
                    'Open Settings',
                    'Cancel'
                );
                if (action === 'Open Settings') {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'dospaces.accessKey');
                }
                return;
            }

            if (!secretKey) {
                const action = await vscode.window.showErrorMessage(
                    'Digital Ocean Spaces Secret Key not configured!',
                    'Open Settings', 
                    'Cancel'
                );
                if (action === 'Open Settings') {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'dospaces.secretKey');
                }
                return;
            }

            if (!bucket) {
                const action = await vscode.window.showErrorMessage(
                    'Digital Ocean Spaces Bucket not configured!',
                    'Open Settings',
                    'Cancel'
                );
                if (action === 'Open Settings') {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'dospaces.bucket');
                }
                return;
            }

            try {
                // Dynamically import AWS SDK to avoid compilation issues
                const { PutObjectCommand, S3Client } = await import('@aws-sdk/client-s3');
                
                // Show progress
                await vscode.window.withProgress({
                    location: vscode.ProgressLocation.Notification,
                    title: "Uploading to Digital Ocean Spaces...",
                    cancellable: false
                }, async (progress) => {
                    progress.report({ increment: 0 });

                    // Create S3 client
                    const s3Client = new S3Client({
                        endpoint: endpoint,
                        forcePathStyle: false,
                        region: region,
                        credentials: {
                            accessKeyId: accessKey,
                            secretAccessKey: secretKey
                        }
                    });

                    // Prepare upload parameters
                    const key = folder ? `${folder}/${fileName}` : fileName;
                    
                    const params: any = {
                        Bucket: bucket,
                        Key: key,
                        Body: content,
                        ContentType: contentType,
                        Metadata: {
                            "uploaded-from": "vscode-extension",
                            "original-filename": fileName || "unknown.txt"
                        }
                    };

                    // Add ACL only if makePublic is true
                    if (makePublic) {
                        params.ACL = 'public-read';
                    }

                    // Upload file
                    const data = await s3Client.send(new PutObjectCommand(params));
                    
                    progress.report({ increment: 100 });
                    
                    // Construct public URL (only show if file is public)
                    const spaceUrl = endpoint.replace('https://', `https://${bucket}.`);
                    // Construct CDN public URL (only show if file is public)
                    const cdnEndpoint = config.get('cdnEndpoint') as string;
                    let publicUrl: string;
                    
                    if (cdnEndpoint) {
                        // Use CDN endpoint if provided - keep the same path structure
                        publicUrl = `${cdnEndpoint}/${key}`;
                    } else {
                        // Fall back to Spaces URL
                        publicUrl = `${spaceUrl}/${key}`;
                    }

                    if (makePublic) {
                        vscode.window.showInformationMessage(
                            `✅ Media file uploaded successfully!`,
                            "Copy URL",
                            "Open in Browser"
                        ).then(selection => {
                            if (selection === "Copy URL") {
                                vscode.env.clipboard.writeText(publicUrl);
                                vscode.window.showInformationMessage("URL copied to clipboard!");
                            } else if (selection === "Open in Browser") {
                                vscode.env.openExternal(vscode.Uri.parse(publicUrl));
                            }
                        });
                    } else {
                        vscode.window.showInformationMessage(`✅ HTML file uploaded successfully (private)`);
                    }
                    
                    return data;
                });

            } catch (error: any) {
                vscode.window.showErrorMessage(`Upload failed: ${error.message}`);
                console.error("Spaces upload error:", error);
            }
        } else {
            // Handle case when no file is selected
            const config = vscode.workspace.getConfiguration("dospaces");
            const accessKey = config.get('accessKey') as string;
            const secretKey = config.get('secretKey') as string;
            const bucket = config.get('bucket') as string;

            // Quick config check for command palette usage
            if (!accessKey || !secretKey || !bucket) {
                const action = await vscode.window.showWarningMessage(
                    'Digital Ocean Spaces configuration incomplete. Please configure your Spaces credentials.',
                    'Open Settings',
                    'Cancel'
                );
                
                if (action === 'Open Settings') {
                    vscode.commands.executeCommand('workbench.action.openSettings', 'dospaces');
                    return;
                }
                return;
            }

            vscode.window.showWarningMessage("Please select a Media file to upload");
        }
    });

    context.subscriptions.push(disposable);
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
EOL

# Create README.md
cat <<EOL > README.md
# Digital Ocean Spaces Uploader

One-click MEDIA file uploader to Digital Ocean Spaces.

## Features

- Upload MEDIA files (['.jpeg', '.jpg', '.mp4', '.mov', '.png']) directly to Digital Ocean Spaces
- Right-click context menu in file explorer and editor
- Configurable Spaces settings
- Public URL generation and copying

## Configuration

1. Open VS Code Settings
2. Search for "Digital Ocean Spaces"
3. Configure:
   - Access Key
   - Secret Key  
   - Endpoint (e.g., https://nyc3.digitaloceanspaces.com)
   - CND Endpoint (e.g., https://mystorage.com)
   - Bucket Name
   - Folder (optional)
   - ACL (public-read recommended for web hosting)

## Usage

- Right-click any Media file in explorer → "Upload Media to Spaces"
- Right-click in Media editor → "Upload Media to Spaces"  
- Command Palette → "Upload Media to Spaces"

## Requirements

- Digital Ocean Spaces account
- Spaces Access Key and Secret Key
- Existing Spaces bucket
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

VSIX_FILE=$(ls dospaces-media-uploader-*.vsix 2>/dev/null | head -n1)

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

echo -e "${GREEN}✅ Digital Ocean Spaces Uploader installed successfully!${NC}"

# Show configuration instructions
echo ""
echo -e "${CYAN}⚙️  Configuration Required:${NC}"
echo "1. Open VS Code Settings (Ctrl+,)"
echo "2. Search for 'Digital Ocean Spaces'"
echo "3. Set your Spaces credentials:"
echo "   - dospaces.accessKey: Your DO Spaces access key"
echo "   - dospaces.secretKey: Your DO Spaces secret key"  
echo "   - dospaces.bucket: Your bucket name"
echo "   - dospaces.endpoint: Your region endpoint"
echo ""
echo -e "${GREEN}🎉 Ready to use! Right-click any Media file → 'Upload Media to Spaces'${NC}"