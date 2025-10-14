#!/bin/bash

# Ask for extension name
read -p "Enter your extension folder name (default: codecollaborator): " EXTNAME
EXTNAME=${EXTNAME:-codecollaborator}

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
mkdir -p "$EXTNAME/src" "$EXTNAME/resources" "$EXTNAME/scripts"
cd "$EXTNAME" || exit

# Create SVG logo
cat <<EOL > resources/logo.svg
<svg width="717px" height="550px" viewBox="0 0 717 550" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
    <title>logo</title>
    <g id="xash3d-fwsg-opengl3d" stroke="none" stroke-width="1" fill="none" fill-rule="evenodd">
        <path d="M146.948296,6.79133333 C163.79663,0.815666667 180.911296,0 195.08563,0 L215.501296,0 C249.927963,0 283.50663,10.68 311.60663,30.5673333 L328.33663,42.4076667 C337.109963,48.6146667 347.589963,51.948 358.333296,51.948 C369.079963,51.948 379.559963,48.6146667 388.329963,42.4073333 L405.059963,30.5676667 C433.159963,10.68 466.739963,0 501.163296,0 L521.579963,0 C535.75663,0 552.869963,0.815666667 569.71663,6.791 C617.82663,23.8536667 655.873296,63.0636667 680.929963,126.504667 C705.729963,189.292 718.463296,277.14 716.463296,395.51 C716.039963,420.493333 712.923296,448.493333 703.31663,473.713333 C693.58663,499.263333 676.583296,523.346667 647.97663,537.026667 C631.703296,544.81 612.523296,550 590.77663,550 C564.54663,550 542.969963,542.443333 526.039963,531.35 C510.293296,521.026667 496.523296,507.683333 484.759963,496.283333 C483.32663,494.893333 481.923296,493.536667 480.549963,492.213333 C467.053296,479.223333 455.70663,469.086667 443.11663,462.556667 C427.20663,454.306667 409.549963,450 391.629963,450 L325.039963,450 C307.11663,450 289.459296,454.306667 273.55063,462.556667 C260.959296,469.086667 249.612296,479.223333 236.116963,492.213333 C234.743963,493.536667 233.341296,494.893333 231.90863,496.283333 C220.144296,507.683333 206.374296,521.026667 190.62563,531.35 C173.69563,542.443333 152.120963,550 125.890296,550 C104.14363,550 84.9622963,544.81 68.6886296,537.026667 C40.0826296,523.346667 23.081963,499.263333 13.3496296,473.713333 C3.74396296,448.493333 0.627629626,420.493333 0.204962959,395.51 C-1.79770371,277.143333 10.9362963,189.292 35.7356296,126.505 C60.7932963,63.064 98.839963,23.8536667 146.948296,6.79133333 Z M195.08563,50 C182.314296,50 172.209296,50.8836667 163.66163,53.915 C132.34663,65.0216667 103.365963,91.3853333 82.2396296,144.872667 C60.854963,199.014 48.2486296,279.446667 50.1976296,394.663333 C50.5712963,416.746667 53.3592963,438.283333 60.074963,455.916667 C66.663963,473.216667 76.401963,485.293333 90.2602963,491.92 C100.451963,496.793333 112.301296,500 125.890296,500 C142.060963,500 154.158296,495.466667 163.216963,489.53 C174.742296,481.976667 184.98563,472.083333 197.290296,460.196667 C198.647963,458.883333 200.030296,457.55 201.44263,456.19 C214.808296,443.323333 230.789963,428.406667 250.53263,418.17 C273.55363,406.23 299.10663,400 325.039963,400 L391.629963,400 C417.559963,400 443.113296,406.23 466.133296,418.17 C485.87663,428.406667 501.859963,443.323333 515.223296,456.19 C516.63663,457.55 518.019963,458.883333 519.37663,460.196667 C531.679963,472.083333 541.923296,481.976667 553.449963,489.53 C562.509963,495.466667 574.60663,500 590.77663,500 C604.36663,500 616.213296,496.793333 626.40663,491.92 C640.26663,485.293333 650.003296,473.216667 656.593296,455.916667 C663.30663,438.283333 666.09663,416.746667 666.469963,394.663333 C668.41663,279.446667 655.813296,199.013667 634.42663,144.872667 C613.299963,91.385 584.319963,65.0213333 553.003296,53.915 C544.45663,50.8836667 534.353296,50 521.579963,50 L501.163296,50 C477.08663,50 453.599963,57.47 433.943296,71.3803333 L417.213296,83.2203333 C399.999963,95.4046667 379.42663,101.948 358.333296,101.948 C337.243296,101.948 316.669963,95.405 299.453296,83.2206667 L282.72363,71.3806667 C263.068296,57.4703333 239.581296,50 215.501296,50 L195.08563,50 Z M208.333296,166.666667 C222.14063,166.666667 233.333296,177.859667 233.333296,191.666667 L233.333296,216.666667 L258.333296,216.666667 C272.14063,216.666667 283.333296,227.86 283.333296,241.666667 C283.333296,255.473333 272.14063,266.666667 258.333296,266.666667 L233.333296,266.666667 L233.333296,291.666667 C233.333296,305.473333 222.14063,316.666667 208.333296,316.666667 C194.526296,316.666667 183.333296,305.473333 183.333296,291.666667 L183.333296,266.666667 L158.333296,266.666667 C144.526296,266.666667 133.333296,255.473333 133.333296,241.666667 C133.333296,227.86 144.526296,216.666667 158.333296,216.666667 L183.333296,216.666667 L183.333296,191.666667 C183.333296,177.859667 194.526296,166.666667 208.333296,166.666667 Z M516.66663,258.333333 C530.473296,258.333333 541.66663,269.526667 541.66663,283.333333 C541.66663,297.14 530.473296,308.333333 516.66663,308.333333 C502.859963,308.333333 491.66663,297.14 491.66663,283.333333 C491.66663,269.526667 502.859963,258.333333 516.66663,258.333333 Z M566.66663,208.333333 C580.473296,208.333333 591.66663,219.526333 591.66663,233.333333 C591.66663,247.14 580.473296,258.333333 566.66663,258.333333 C552.859963,258.333333 541.66663,247.14 541.66663,233.333333 C541.66663,219.526333 552.859963,208.333333 566.66663,208.333333 Z M466.66663,208.333333 C480.473296,208.333333 491.66663,219.526333 491.66663,233.333333 C491.66663,247.14 480.473296,258.333333 466.66663,258.333333 C452.859963,258.333333 441.66663,247.14 441.66663,233.333333 C441.66663,219.526333 452.859963,208.333333 466.66663,208.333333 Z M516.66663,158.333333 C530.473296,158.333333 541.66663,169.526333 541.66663,183.333333 C541.66663,197.140333 530.473296,208.333333 516.66663,208.333333 C502.859963,208.333333 491.66663,197.140333 491.66663,183.333333 C491.66663,169.526333 502.859963,158.333333 516.66663,158.333333 Z" id="logo" fill="#FFFFFF"></path>
    </g>
</svg>
EOL

# Create package.json
cat <<EOL > package.json
{
  "name": "$EXTNAME",
  "displayName": "Code Collaborator",
  "publisher": "songdropltd",
  "description": "Advanced VS Code extension for file analysis, vector search, and collaborative code comments",
  "icon": "resources/logo.png",
  "version": "1.0.0",
  "engines": { "vscode": "^1.81.0" },
  "activationEvents": ["onView:codeCollaboratorView"],
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
          "id": "codeCollaboratorActivity",
          "title": "Code Collaborator",
          "icon": "resources/logo.svg"
        }
      ]
    },
    "views": {
      "codeCollaboratorActivity": [
        {
          "id": "codeCollaboratorView",
          "name": "Code Collaborator",
          "type": "webview",
          "icon": "resources/logo.svg"
        }
      ]
    },
    "commands": [
      {
        "command": "codeCollaborator.addComment",
        "title": "Add Code Comment",
        "category": "Code Collaborator"
      },
      {
        "command": "codeCollaborator.applySolution", 
        "title": "Apply Solution",
        "category": "Code Collaborator"
      }
    ]
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
    "types": ["node"]
  },
  "exclude": ["node_modules", ".vscode-test"]
}
EOL

# Create src/extension.ts
cat <<'EOL' > src/extension.ts
import * as vscode from "vscode";
import { CodeCollaboratorPanel } from "./webview";

export function activate(context: vscode.ExtensionContext) {
    const provider = new CodeCollaboratorPanel(context);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider("codeCollaboratorView", provider)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('codeCollaborator.addComment', () => {
            provider.addCommentToCurrentFile();
        }),
        vscode.commands.registerCommand('codeCollaborator.applySolution', () => {
            provider.applySolutionFromCurrentFile();
        })
    );
}

export function deactivate() {}
EOL

# Create src/generate_html.ts with ALL features
cat <<'EOL' > src/generate_html.ts
export function generateHtml(nonce: string, cspSource: string): string {
  return `
   <!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'none'; style-src ${cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
  <title>Code Collaborator</title>
  <style>
    body { 
      font-family: sans-serif; 
      padding: 16px; 
      background: var(--vscode-sideBar-background);
      color: white;
    }
    
    h3 { 
      margin: 0 0 16px 0; 
      color: white;
    }

    .tabs {
        position: relative;
        display: block; /* instead of flex */
        overflow: hidden;
        overflow-x: auto;
        white-space: nowrap;
        height: 40px;
        scrollbar-width: none; /* Firefox */
        border-bottom: 1px solid var(--vscode-panel-border);
        margin-bottom: 0px;
    }
            
    .tabs::-webkit-scrollbar {
        display: none; /* hide scrollbar in Chrome/Safari */
    }
    
    .tab {
      display: inline-block; /* instead of flex */
      padding: 8px 16px;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
    }
    
    .tab.active {
      border-bottom-color: var(--vscode-button-background);
      color: var(--vscode-button-background);
    }
    
    .tab-content {
      display: none;
    }
    
    .tab-content.active {
      display: block;
    }
    
    .form-group {
      margin-bottom: 2px;
    }
    
    label {
      display: block;
      margin-bottom: 4px;
      font-size: 12px;
      font-weight: 600;
      color: var(--vscode-descriptionForeground);
    }
    
    select, button, input, textarea {
      width: 100%;
      padding: 8px 12px;
      font-size: 13px;
      border: 1px solid var(--vscode-input-border);
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border-radius: 3px;
      box-sizing: border-box;
    }
    
    textarea {
      min-height: 80px;
      resize: vertical;
    }
    
    button { 
      cursor: pointer; 
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border: none;
      font-weight: 600;
      margin-top: 2px;
    }
    
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    
    button:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    
    .secondary {
      background: var(--vscode-button-secondaryBackground);
      color: var(--vscode-button-secondaryForeground);
    }
    
    .success {
      background: var(--vscode-testing-iconPassed);
    }
    
    .loader {
      display: none;
      width: 20px;
      height: 20px;
      border: 2px solid var(--vscode-button-foreground);
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
    
    .success-text { color: var(--vscode-testing-iconPassed); }
    .error { color: var(--vscode-testing-iconFailed); }
    .warning { color: var(--vscode-testing-iconQueued); }
    
    .output-links {
      display: none;
      margin-top: 12px;
      font-size: 12px;
    }
    
    .output-links a {
      color: var(--vscode-textLink-foreground);
      text-decoration: none;
      display: block;
      margin: 4px 0;
      padding: 4px 8px;
      background: var(--vscode-button-secondaryBackground);
      border-radius: 3px;
    }
    
    .output-links a:hover {
      background: var(--vscode-button-secondaryHoverBackground);
      text-decoration: underline;
    }
    
    .info-text {
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      margin-top: 16px;
      line-height: 1.4;
    }
    
    .search-results {
      max-height: 300px;
      overflow-y: auto;
      border: 1px solid var(--vscode-input-border);
      border-radius: 3px;
      padding: 8px;
      margin-top: 8px;
      display: none;
    }
    
    .search-result {
      padding: 8px;
      border-bottom: 1px solid var(--vscode-panel-border);
      cursor: pointer;
    }
    
    .search-result:hover {
      background: var(--vscode-list-hoverBackground);
    }
    
    .search-result:last-child {
      border-bottom: none;
    }
    
    .result-file {
      font-weight: 600;
      font-size: 12px;
    }
    
    .result-content {
      font-size: 11px;
      color: var(--vscode-descriptionForeground);
      margin-top: 4px;
    }
    
    .result-score {
      float: right;
      font-size: 10px;
      color: var(--vscode-testing-iconPassed);
    }
    
    .checkbox-group {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 8px 0;
    }
    
    .checkbox-group input {
      width: auto;
    }
    
    .progress-bar {
      width: 100%;
      height: 4px;
      background: var(--vscode-input-border);
      border-radius: 2px;
      margin: 8px 0;
      overflow: hidden;
      display: none;
    }
    
    .progress-fill {
      height: 100%;
      background: var(--vscode-testing-iconPassed);
      width: 0%;
      transition: width 0.3s ease;
    }
    
    /* Comments Section */
    .comments-section {
      margin-top: 16px;
    }
    
    .comment {
      background: var(--vscode-input-background);
      border: 1px solid var(--vscode-input-border);
      border-radius: 4px;
      padding: 12px;
      margin-bottom: 8px;
    }
    
    .comment-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }
    
    .comment-author {
      font-weight: 600;
      font-size: 12px;
    }
    
    .comment-timestamp {
      font-size: 10px;
      color: var(--vscode-descriptionForeground);
    }
    
    .comment-message {
      font-size: 12px;
      line-height: 1.4;
    }
    
    .comment-actions {
      margin-top: 8px;
      display: flex;
      gap: 8px;
    }
    
    .apply-btn {
      background: var(--vscode-testing-iconPassed);
      font-size: 11px;
      padding: 4px 8px;
    }
    
    .diff-preview {
      background: var(--vscode-textCodeBlock-background);
      border: 1px solid var(--vscode-input-border);
      border-radius: 3px;
      padding: 8px;
      margin-top: 8px;
      font-family: monospace;
      font-size: 11px;
      white-space: pre-wrap;
      max-height: 200px;
      overflow-y: auto;
    }
    
    .diff-added {
      color: var(--vscode-gitDecoration-addedResourceForeground);
      background: color-mix(in srgb, var(--vscode-gitDecoration-addedResourceForeground) 10%, transparent);
    }
    
    .diff-removed {
      color: var(--vscode-gitDecoration-deletedResourceForeground);
      background: color-mix(in srgb, var(--vscode-gitDecoration-deletedResourceForeground) 10%, transparent);
    }
    
    .new-comment-form {
      margin-top: 16px;
    }
    
    .comment-type-selector {
      display: flex;
      gap: 8px;
      margin-bottom: 8px;
    }
    
    .comment-type-btn {
      flex: 1;
      padding: 6px 12px;
      font-size: 11px;
    }
    
    .comment-type-btn.active {
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
    }
  </style>
</head>
<body>
  <h3>
    <svg width="40px" height="31px" viewBox="0 0 40 31" version="1.1" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
        <title>logo</title>
        <g id="xash3d-fwsg-opengl3d" stroke="none" stroke-width="1" fill="none" fill-rule="evenodd">
            <path d="M8.20175289,0.379050586 C9.14212355,0.0455255121 10.0973593,0 10.8884837,0 L12.027961,0 C13.9494465,0 15.8236017,0.596092116 17.3919715,1.70608112 L18.3257375,2.36693593 C18.8154111,2.71337261 19.4003405,2.89941884 19.9999675,2.89941884 C20.5997805,2.89941884 21.1847099,2.71337261 21.6741975,2.36691733 L22.6079635,1.70609973 C24.1763332,0.596092116 26.0505629,0 27.9718623,0 L29.1113955,0 C29.9026501,0 30.8578114,0.0455255121 31.7980891,0.379031981 C34.4832943,1.33136541 36.6068259,3.5198272 38.0053354,7.06071483 C39.3895194,10.5651188 40.100216,15.4682555 39.9885882,22.0749431 C39.9649603,23.4693596 39.7910071,25.0321479 39.2548219,26.4397737 C38.7117529,27.865818 37.7627311,29.210002 36.1660824,29.9735358 C35.2578047,30.4079537 34.1872947,30.6976277 32.9735291,30.6976277 C31.5095314,30.6976277 30.3052541,30.2758609 29.3603253,29.656699 C28.4814429,29.0805139 27.712886,28.3357708 27.0563288,27.6994927 C26.976329,27.6219114 26.8980035,27.5461906 26.8213524,27.4723303 C26.0680513,26.7473081 25.4347499,26.1815415 24.7320533,25.817077 C23.8440547,25.3566126 22.8585678,25.1162408 21.8583833,25.1162408 L18.1417378,25.1162408 C17.1413672,25.1162408 16.1558431,25.3566126 15.2679189,25.817077 C14.5651479,26.1815415 13.9318279,26.7473081 13.1786011,27.4723303 C13.1019687,27.5461906 13.0236804,27.6219114 12.9437178,27.6994927 C12.2871048,28.3357708 11.5185478,29.0805139 10.6395538,29.656699 C9.69462503,30.2758609 8.49045942,30.6976277 7.02642444,30.6976277 C5.81265885,30.6976277 4.74207443,30.4079537 3.83377814,29.9735358 C2.23716662,29.210002 1.28829365,27.865818 0.745094473,26.4397737 C0.208965056,25.0321479 0.0350304374,23.4693596 0.0114397756,22.0749431 C-0.100336798,15.4684416 0.610397003,10.5651188 1.99454373,7.06073344 C3.39310905,3.5198458 5.5166407,1.33136541 8.20175289,0.379050586 Z M10.8884837,2.79069343 C10.1756662,2.79069343 9.61166702,2.84001428 9.13458868,3.00920472 C7.38677738,3.62911075 5.76925427,5.10056898 4.59011187,8.08590397 C3.3965509,11.1077412 2.69294267,15.5969995 2.8017239,22.0276874 C2.82257968,23.2602437 2.97818875,24.4622883 3.35301608,25.4464729 C3.72077366,26.4120528 4.26428911,27.0860983 5.03777631,27.4559582 C5.60661265,27.7279578 6.26796979,27.9069343 7.02642444,27.9069343 C7.92897191,27.9069343 8.60417088,27.6539114 9.10977011,27.3225631 C9.75304355,26.9009823 10.3247636,26.3487971 11.0115347,25.6853562 C11.0873113,25.612054 11.1644647,25.5376355 11.2432924,25.4617287 C11.989282,24.7435902 12.8812806,23.9110334 13.9831952,23.3396854 C15.2680863,22.6732678 16.6942981,22.3255474 18.1417378,22.3255474 L21.8583833,22.3255474 C23.3056369,22.3255474 24.7318673,22.6732678 26.0167025,23.3396854 C27.1186543,23.9110334 28.010746,24.7435902 28.7566053,25.4617287 C28.8354889,25.5376355 28.9126981,25.612054 28.9884189,25.6853562 C29.6751155,26.3487971 30.2468356,26.9009823 30.8901835,27.3225631 C31.3958571,27.6539114 32.0710189,27.9069343 32.9735291,27.9069343 C33.7320396,27.9069343 34.3932479,27.7279578 34.9621773,27.4559582 C35.7357575,27.0860983 36.2791985,26.4120528 36.6470119,25.4464729 C37.021709,24.4622883 37.1774297,23.2602437 37.1982669,22.0276874 C37.3069179,15.5969995 36.6034771,11.1077226 35.4098045,8.08590397 C34.2306435,5.10055037 32.6131576,3.62909215 30.8652533,3.00920472 C30.3882307,2.84001428 29.8243246,2.79069343 29.1113955,2.79069343 L27.9718623,2.79069343 C26.6280504,2.79069343 25.3171687,3.20762302 24.2200541,3.98401254 L23.2862881,4.64484874 C22.3255453,5.32490352 21.177268,5.69011227 19.9999675,5.69011227 C18.822853,5.69011227 17.6745757,5.32492213 16.7136469,4.64486735 L15.7798995,3.98403114 C14.6828593,3.20764163 13.371959,2.79069343 12.027961,2.79069343 L10.8884837,2.79069343 Z M11.6278872,9.30231142 C12.3985279,9.30231142 13.0232339,9.92703605 13.0232339,10.6976581 L13.0232339,12.0930048 L14.4185806,12.0930048 C15.1892213,12.0930048 15.8139273,12.7177481 15.8139273,13.4883516 C15.8139273,14.258955 15.1892213,14.8836983 14.4185806,14.8836983 L13.0232339,14.8836983 L13.0232339,16.279045 C13.0232339,17.0496485 12.3985279,17.6743917 11.6278872,17.6743917 C10.8572651,17.6743917 10.2325405,17.0496485 10.2325405,16.279045 L10.2325405,14.8836983 L8.83719378,14.8836983 C8.0665717,14.8836983 7.44184707,14.258955 7.44184707,13.4883516 C7.44184707,12.7177481 8.0665717,12.0930048 8.83719378,12.0930048 L10.2325405,12.0930048 L10.2325405,10.6976581 C10.2325405,9.92703605 10.8572651,9.30231142 11.6278872,9.30231142 Z M28.8371633,14.4185827 C29.6077668,14.4185827 30.23251,15.0433259 30.23251,15.8139294 C30.23251,16.5845329 29.6077668,17.2092761 28.8371633,17.2092761 C28.0665599,17.2092761 27.4418166,16.5845329 27.4418166,15.8139294 C27.4418166,15.0433259 28.0665599,14.4185827 28.8371633,14.4185827 Z M31.6278568,11.6278893 C32.3984602,11.6278893 33.0232035,12.2526139 33.0232035,13.023236 C33.0232035,13.7938395 32.3984602,14.4185827 31.6278568,14.4185827 C30.8572533,14.4185827 30.23251,13.7938395 30.23251,13.023236 C30.23251,12.2526139 30.8572533,11.6278893 31.6278568,11.6278893 Z M26.0464699,11.6278893 C26.8170734,11.6278893 27.4418166,12.2526139 27.4418166,13.023236 C27.4418166,13.7938395 26.8170734,14.4185827 26.0464699,14.4185827 C25.2758664,14.4185827 24.6511232,13.7938395 24.6511232,13.023236 C24.6511232,12.2526139 25.2758664,11.6278893 26.0464699,11.6278893 Z M28.8371633,8.83719585 C29.6077668,8.83719585 30.23251,9.46192048 30.23251,10.2325426 C30.23251,11.0031646 29.6077668,11.6278893 28.8371633,11.6278893 C28.0665599,11.6278893 27.4418166,11.0031646 27.4418166,10.2325426 C27.4418166,9.46192048 28.0665599,8.83719585 28.8371633,8.83719585 Z" id="logo" fill="#FFFFFF"></path>
        </g>
    </svg>
    Code Collaborator
  </h3>
  
  <div class="tabs">
    <div class="tab active" data-tab="comments">Code Comments</div>
    <div class="tab" data-tab="fileList">File Lister</div>
    <div class="tab" data-tab="vectorDb">Vector Database</div>
    <div class="tab" data-tab="search">Semantic Search</div>
  </div>
  
  <!-- Code Comments Tab -->
  <div class="tab-content active" id="commentsTab">
    <div class="form-group">
      <label for="currentFile">Current File:</label>
      <input type="text" id="currentFile" readonly placeholder="No file selected">
    </div>
    
    <div class="comments-section" id="commentsSection">
      <div class="comment" id="noCommentsMessage">
        <div class="comment-message">No comments yet for this file. Be the first to add one!</div>
      </div>
    </div>
    
    <div class="new-comment-form">
      <div class="comment-type-selector">
        <button class="comment-type-btn active" data-type="request">Help Request</button>
        <button class="comment-type-btn" data-type="solution">Solution</button>
        <button class="comment-type-btn" data-type="feedback">Feedback</button>
      </div>
      
      <textarea id="newComment" placeholder="Type your comment here... For solutions, you can include diff format:&#10;&#10;--- file.c&#10;+++ file.c&#10;@@ -1,3 +1,4 @@&#10; void function() {&#10;+    // new code&#10;-    // old code&#10; }"></textarea>
      
      <div class="form-group">
        <label for="commentDiff">Optional Diff (for solutions):</label>
        <textarea id="commentDiff" placeholder="Paste unified diff here..." style="font-family: monospace; font-size: 11px;"></textarea>
      </div>
      
      <button id="addCommentBtn" class="success">Add Comment</button>
    </div>
  </div>

  <!-- File List Tab -->
  <div class="tab-content" id="fileListTab">
    <div class="form-group">
      <label for="folder">Scan Folder:</label>
      <select id="folder">
        <option value="workspace">Entire Workspace</option>
      </select>
    </div>
    
    <div class="form-group">
      <label for="format">Output Format:</label>
      <select id="format">
        <option value="json">JSON</option>
        <option value="ai_json">AI Format JSON</option>
        <option value="txt">Text File</option>
        <option value="xml">XML</option>
        <option value="csv">CSV</option>
      </select>
    </div>
    
    <div class="checkbox-group">
      <input type="checkbox" id="includeHidden" checked>
      <label for="includeHidden" style="margin: 0; font-weight: normal;">Include hidden files</label>
    </div>
    
    <button id="generateFileList">Generate File List</button>
    <div class="loader" id="fileListLoader"></div>
    <div class="status" id="fileListStatus"></div>
    
    <div class="output-links" id="fileListOutput">
      <a href="#" id="openFolder">📁 Open Output Folder</a>
      <a href="#" id="openFile">📄 Open Generated File</a>
    </div>
  </div>
  
  <!-- Vector Database Tab -->
  <div class="tab-content" id="vectorDbTab">
    <div class="form-group">
      <label for="vectorFolder">Source Folder:</label>
      <select id="vectorFolder">
        <option value="workspace">Entire Workspace</option>
      </select>
    </div>
    
    <div class="form-group">
      <label for="fileTypes">File Types to Process:</label>
      <select id="fileTypes" multiple style="height: 100px;">
        <option value="py" selected>Python (.py)</option>
        <option value="js" selected>JavaScript (.js)</option>
        <option value="ts" selected>TypeScript (.ts)</option>
        <option value="java" selected>Java (.java)</option>
        <option value="cpp" selected>C++ (.cpp)</option>
        <option value="c" selected>C (.c)</option>
        <option value="rb" selected>Ruby (.rb)</option>
        <option value="php" selected>PHP (.php)</option>
        <option value="go" selected>Go (.go)</option>
        <option value="md" selected>Markdown (.md)</option>
        <option value="txt" selected>Text (.txt)</option>
        <option value="json" selected>JSON (.json)</option>
        <option value="yaml" selected>YAML (.yaml, .yml)</option>
        <option value="xml" selected>XML (.xml)</option>
        <option value="html" selected>HTML (.html)</option>
        <option value="css" selected>CSS (.css)</option>
      </select>
    </div>
    
    <div class="form-group">
      <label for="chunkSize">Chunk Size (tokens):</label>
      <input type="number" id="chunkSize" value="512" min="100" max="2048">
    </div>
    
    <button id="createVectorDb">Create Vector Database</button>
    <div class="progress-bar" id="vectorProgress">
      <div class="progress-fill" id="vectorProgressFill"></div>
    </div>
    <div class="loader" id="vectorLoader"></div>
    <div class="status" id="vectorStatus"></div>
  </div>
  
  <!-- Semantic Search Tab -->
  <div class="tab-content" id="searchTab">
    <div class="form-group">
      <label for="searchQuery">Search Query:</label>
      <input type="text" id="searchQuery" placeholder="e.g., authentication logic or database connection">
    </div>
    
    <div class="form-group">
      <label for="resultCount">Number of Results:</label>
      <input type="number" id="resultCount" value="10" min="1" max="50">
    </div>
    
    <div class="form-group">
      <label for="fileTypeFilter">Filter by File Type:</label>
      <select id="fileTypeFilter">
        <option value="">All Files</option>
        <option value="py">Python</option>
        <option value="js">JavaScript</option>
        <option value="ts">TypeScript</option>
        <option value="md">Documentation</option>
        <option value="java">Java</option>
      </select>
    </div>
    
    <button id="performSearch">Search Codebase</button>
    <div class="loader" id="searchLoader"></div>
    <div class="status" id="searchStatus"></div>
    
    <div class="search-results" id="searchResults"></div>
  </div>
  
  
  
  <div class="info-text">
    <strong>Code Collaborator</strong><br>
    • List files with multiple output formats<br>
    • Create semantic vector databases<br>
    • Search codebase with natural language<br>
    • Collaborative code comments with one-click apply
  </div>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    let currentTab = 'fileList';
    let currentFileComments = [];
    
    // Tab management
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const tabName = tab.dataset.tab;
        switchTab(tabName);
      });
    });
    
    function switchTab(tabName) {
      currentTab = tabName;
      
      // Update active tab
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      
      document.querySelector(\`[data-tab="\${tabName}"]\`).classList.add('active');
      document.getElementById(\`\${tabName}Tab\`).classList.add('active');
      
      // Refresh data when switching to comments tab
      if (tabName === 'comments') {
        vscode.postMessage({ command: 'getCurrentFileComments' });
      } else if (tabName === 'fileList' || tabName === 'vectorDb') {
        vscode.postMessage({ command: 'getFolders' });
      }
    }
    
    // File List functionality
    const generateFileListBtn = document.getElementById('generateFileList');
    const folderSelect = document.getElementById('folder');
    const formatSelect = document.getElementById('format');
    const fileListLoader = document.getElementById('fileListLoader');
    const fileListStatus = document.getElementById('fileListStatus');
    const fileListOutput = document.getElementById('fileListOutput');
    const openFolder = document.getElementById('openFolder');
    const openFile = document.getElementById('openFile');
    
    let currentOutputFile = '';
    
    generateFileListBtn.addEventListener('click', () => {
      const folder = folderSelect.value;
      const format = formatSelect.value;
      const includeHidden = document.getElementById('includeHidden').checked;
      
      generateFileListBtn.disabled = true;
      fileListLoader.style.display = 'block';
      fileListStatus.textContent = 'Generating file list...';
      fileListStatus.className = 'status';
      fileListOutput.style.display = 'none';
      
      vscode.postMessage({ 
        command: 'generateFileList',
        folder: folder,
        format: format,
        includeHidden: includeHidden
      });
    });
    
    // Vector Database functionality
    const createVectorDbBtn = document.getElementById('createVectorDb');
    const vectorFolderSelect = document.getElementById('vectorFolder');
    const vectorLoader = document.getElementById('vectorLoader');
    const vectorStatus = document.getElementById('vectorStatus');
    const vectorProgress = document.getElementById('vectorProgress');
    const vectorProgressFill = document.getElementById('vectorProgressFill');
    
    createVectorDbBtn.addEventListener('click', () => {
      const folder = vectorFolderSelect.value;
      const fileTypes = Array.from(document.getElementById('fileTypes').selectedOptions)
        .map(opt => opt.value);
      const chunkSize = parseInt(document.getElementById('chunkSize').value);
      
      createVectorDbBtn.disabled = true;
      vectorLoader.style.display = 'block';
      vectorProgress.style.display = 'block';
      vectorStatus.textContent = 'Creating vector database...';
      vectorStatus.className = 'status';
      
      vscode.postMessage({ 
        command: 'createVectorDb',
        folder: folder,
        fileTypes: fileTypes,
        chunkSize: chunkSize
      });
    });
    
    // Search functionality
    const performSearchBtn = document.getElementById('performSearch');
    const searchQuery = document.getElementById('searchQuery');
    const searchLoader = document.getElementById('searchLoader');
    const searchStatus = document.getElementById('searchStatus');
    const searchResults = document.getElementById('searchResults');
    
    performSearchBtn.addEventListener('click', () => {
      const query = searchQuery.value.trim();
      const resultCount = parseInt(document.getElementById('resultCount').value);
      const fileTypeFilter = document.getElementById('fileTypeFilter').value;
      
      if (!query) {
        searchStatus.textContent = 'Please enter a search query';
        searchStatus.className = 'status error';
        return;
      }
      
      performSearchBtn.disabled = true;
      searchLoader.style.display = 'block';
      searchStatus.textContent = 'Searching...';
      searchStatus.className = 'status';
      searchResults.style.display = 'none';
      
      vscode.postMessage({ 
        command: 'semanticSearch',
        query: query,
        resultCount: resultCount,
        fileTypeFilter: fileTypeFilter
      });
    });
    
    // Allow Enter key for search
    searchQuery.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        performSearchBtn.click();
      }
    });
    
    // Common event listeners
    openFolder.addEventListener('click', (e) => {
      e.preventDefault();
      vscode.postMessage({ command: 'openFolder' });
    });
    
    openFile.addEventListener('click', (e) => {
      e.preventDefault();
      if (currentOutputFile) {
        vscode.postMessage({ command: 'openFile', filePath: currentOutputFile });
      }
    });
    
    // Comments functionality
    const currentFileInput = document.getElementById('currentFile');
    const commentsSection = document.getElementById('commentsSection');
    const noCommentsMessage = document.getElementById('noCommentsMessage');
    const newCommentText = document.getElementById('newComment');
    const commentDiff = document.getElementById('commentDiff');
    const addCommentBtn = document.getElementById('addCommentBtn');
    const commentTypeBtns = document.querySelectorAll('.comment-type-btn');
    
    let currentCommentType = 'request';
    
    // Comment type selection
    commentTypeBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        commentTypeBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentCommentType = btn.dataset.type;
        
        // Show/hide diff area based on type
        commentDiff.parentElement.style.display = currentCommentType === 'solution' ? 'block' : 'none';
      });
    });
    
    // Add new comment
    addCommentBtn.addEventListener('click', () => {
      const message = newCommentText.value.trim();
      const diff = commentDiff.value.trim();
      
      if (!message) {
        vscode.postMessage({ 
          command: 'showError', 
          message: 'Please enter a comment message' 
        });
        return;
      }
      
      vscode.postMessage({
        command: 'addComment',
        type: currentCommentType,
        message: message,
        diff: diff || undefined
      });
      
      // Clear form
      newCommentText.value = '';
      commentDiff.value = '';
    });
    
    // Apply solution
    function applySolution(commentId) {
      vscode.postMessage({
        command: 'applySolution',
        commentId: commentId
      });
    }
    
    // Display comments
    function displayComments(comments) {
      commentsSection.innerHTML = '';
      
      if (comments.length === 0) {
        commentsSection.appendChild(noCommentsMessage);
        noCommentsMessage.style.display = 'block';
        return;
      }
      
      noCommentsMessage.style.display = 'none';
      
      comments.forEach(comment => {
        const commentEl = document.createElement('div');
        commentEl.className = 'comment';
        
        const header = document.createElement('div');
        header.className = 'comment-header';
        
        const author = document.createElement('div');
        author.className = 'comment-author';
        author.textContent = \`\${comment.username} (\${comment.type})\`;
        
        const timestamp = document.createElement('div');
        timestamp.className = 'comment-timestamp';
        timestamp.textContent = new Date(comment.timestamp).toLocaleString();
        
        header.appendChild(author);
        header.appendChild(timestamp);
        
        const message = document.createElement('div');
        message.className = 'comment-message';
        message.textContent = comment.message;
        
        commentEl.appendChild(header);
        commentEl.appendChild(message);
        
        // Show diff if available
        if (comment.diff) {
          const diffPreview = document.createElement('div');
          diffPreview.className = 'diff-preview';
          diffPreview.textContent = comment.diff;
          commentEl.appendChild(diffPreview);
        }
        
        // Add actions for solutions
        if (comment.type === 'solution') {
          const actions = document.createElement('div');
          actions.className = 'comment-actions';
          
          const applyBtn = document.createElement('button');
          applyBtn.className = 'apply-btn';
          applyBtn.textContent = 'Apply Solution';
          applyBtn.addEventListener('click', () => applySolution(comment.id));
          
          actions.appendChild(applyBtn);
          commentEl.appendChild(actions);
        }
        
        commentsSection.appendChild(commentEl);
      });
    }
    
    // Handle messages from extension
    window.addEventListener('message', event => {
      const message = event.data;
      
      switch (message.command) {
        case 'foldersList':
          // Populate folder dropdowns
          const folders = message.folders;
          folderSelect.innerHTML = '<option value="workspace">Entire Workspace</option>';
          vectorFolderSelect.innerHTML = '<option value="workspace">Entire Workspace</option>';
          
          folders.forEach(folder => {
            const option1 = document.createElement('option');
            option1.value = folder.path;
            option1.textContent = folder.name;
            folderSelect.appendChild(option1);
            
            const option2 = document.createElement('option');
            option2.value = folder.path;
            option2.textContent = folder.name;
            vectorFolderSelect.appendChild(option2);
          });
          break;
          
        case 'fileListStarted':
          generateFileListBtn.disabled = true;
          fileListLoader.style.display = 'block';
          fileListStatus.textContent = 'Generating file list...';
          break;
          
        case 'fileListSuccess':
          generateFileListBtn.disabled = false;
          fileListLoader.style.display = 'none';
          fileListStatus.textContent = '✅ File list generated successfully!';
          fileListStatus.className = 'status success-text';
          fileListOutput.style.display = 'block';
          currentOutputFile = message.filePath;
          break;
          
        case 'fileListError':
          generateFileListBtn.disabled = false;
          fileListLoader.style.display = 'none';
          fileListStatus.textContent = '❌ ' + message.error;
          fileListStatus.className = 'status error';
          break;
          
        case 'vectorDbProgress':
          vectorProgressFill.style.width = message.progress + '%';
          vectorStatus.textContent = message.message;
          break;
          
        case 'vectorDbSuccess':
          createVectorDbBtn.disabled = false;
          vectorLoader.style.display = 'none';
          vectorProgress.style.display = 'none';
          vectorStatus.textContent = '✅ Vector database created successfully!';
          vectorStatus.className = 'status success-text';
          break;
          
        case 'vectorDbError':
          createVectorDbBtn.disabled = false;
          vectorLoader.style.display = 'none';
          vectorProgress.style.display = 'none';
          vectorStatus.textContent = '❌ ' + message.error;
          vectorStatus.className = 'status error';
          break;
          
        case 'searchResults':
          performSearchBtn.disabled = false;
          searchLoader.style.display = 'none';
          searchStatus.textContent = 'Found ' + message.results.length + ' results';
          searchStatus.className = 'status success-text';
          searchResults.style.display = 'block';
          
          searchResults.innerHTML = '';
          message.results.forEach((result, index) => {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'search-result';
            const scorePercent = (result.score * 100).toFixed(1);
            resultDiv.innerHTML = '<div class="result-file">' +
              '<span class="result-score">' + scorePercent + '%</span>' +
              result.file +
              '</div>' +
              '<div class="result-content">' + 
              (result.content.length > 200 ? result.content.substring(0, 200) + '...' : result.content) +
              '</div>';
            
            resultDiv.addEventListener('click', () => {
              vscode.postMessage({ 
                command: 'openFile', 
                filePath: result.file 
              });
            });
            
            searchResults.appendChild(resultDiv);
          });
          break;
          
        case 'searchError':
          performSearchBtn.disabled = false;
          searchLoader.style.display = 'none';
          searchStatus.textContent = '❌ ' + message.error;
          searchStatus.className = 'status error';
          break;
          
        case 'currentFileComments':
          currentFileInput.value = message.file || 'No file selected';
          currentFileComments = message.comments || [];
          displayComments(currentFileComments);
          break;
          
        case 'commentAdded':
          vscode.postMessage({ command: 'getCurrentFileComments' });
          break;
          
        case 'solutionApplied':
          vscode.postMessage({ 
            command: 'showInfo', 
            message: 'Solution applied successfully!' 
          });
          break;
          
        case 'showError':
          // Could show a toast notification
          console.error('Error:', message.message);
          break;
      }
    });
    
    // Initial load - get folders and current file comments
    vscode.postMessage({ command: 'getFolders' });
    vscode.postMessage({ command: 'getCurrentFileComments' });
  </script>
</body>
</html>
  `;
}
EOL

# Create the enhanced webview with ALL functionality
cat <<'EOL' > src/webview.ts
import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import { exec } from "child_process";
import { platform } from "os";
import { generateHtml } from "./generate_html";

interface Comment {
    id: number;
    username: string;
    timestamp: string;
    type: 'request' | 'solution' | 'feedback';
    message: string;
    diff?: string;
    status?: 'pending' | 'applied' | 'rejected';
}

export class CodeCollaboratorPanel implements vscode.WebviewViewProvider {
    private _view?: vscode.WebviewView;
    private _context: vscode.ExtensionContext;
    private _disposables: vscode.Disposable[] = [];

    constructor(private readonly context: vscode.ExtensionContext) {
        this._context = context;
        
        // Listen for active text editor changes
        vscode.window.onDidChangeActiveTextEditor((editor) => {
            this.onActiveFileChanged(editor);
        }, null, this._disposables);
    }

    resolveWebviewView(webviewView: vscode.WebviewView, _context: vscode.WebviewViewResolveContext, _token: vscode.CancellationToken) {
        this._view = webviewView;
        webviewView.webview.options = { enableScripts: true };

        const nonce = this.getNonce();
        const cspSource = webviewView.webview.cspSource;
        webviewView.webview.html = generateHtml(nonce, cspSource);

        webviewView.webview.onDidReceiveMessage(async message => {
            switch (message.command) {
                case 'getFolders':
                    await this.sendFolderList();
                    break;
                case 'generateFileList':
                    await this.generateFileList(message.folder, message.format, message.includeHidden);
                    break;
                case 'createVectorDb':
                    await this.createVectorDatabase(message.folder, message.fileTypes, message.chunkSize);
                    break;
                case 'semanticSearch':
                    await this.semanticSearch(message.query, message.resultCount, message.fileTypeFilter);
                    break;
                case 'openFolder':
                    await this.openOutputFolder();
                    break;
                case 'openFile':
                    await this.openFile(message.filePath);
                    break;
                case 'getCurrentFileComments':
                    await this.sendCurrentFileComments();
                    break;
                case 'addComment':
                    await this.addComment(message.type, message.message, message.diff);
                    break;
                case 'applySolution':
                    await this.applySolution(message.commentId);
                    break;
                case 'showError':
                    vscode.window.showErrorMessage(message.message);
                    break;
                case 'showInfo':
                    vscode.window.showInformationMessage(message.message);
                    break;
                case 'switchToComments':
                    // This would require more complex tab management
                    break;
            }
        });

        // Send initial file comments when webview is ready
        setTimeout(() => {
            this.sendCurrentFileComments();
        }, 500);
    }

    private async onActiveFileChanged(editor: vscode.TextEditor | undefined) {
        // Update comments when active file changes
        await this.sendCurrentFileComments();
    }

    private async sendFolderList() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return;
        }

        const workspacePath = workspaceFolder.uri.fsPath;
        const folders = await this.getSubfolders(workspacePath);
        
        this._view?.webview.postMessage({ 
            command: 'foldersList', 
            folders: folders
        });
    }

    private async getSubfolders(rootPath: string): Promise<{name: string, path: string}[]> {
        const folders: {name: string, path: string}[] = [];
        
        try {
            const entries = await vscode.workspace.fs.readDirectory(vscode.Uri.file(rootPath));
            
            for (const [name, type] of entries) {
                if (type === vscode.FileType.Directory && 
                    !name.startsWith('.') && 
                    !name.startsWith('myenv') && 
                    name !== '__pycache__' &&
                    name !== 'node_modules' &&
                    name !== '.git') {
                    
                    const fullPath = path.join(rootPath, name);
                    folders.push({
                        name: name,
                        path: fullPath
                    });
                }
            }
        } catch (error) {
            console.error('Error reading folders:', error);
        }
        
        return folders;
    }

    private async generateFileList(selectedFolder: string, format: string, includeHidden: boolean) {
        this._view?.webview.postMessage({ command: 'fileListStarted' });

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            const error = "No workspace folder open!";
            this._view?.webview.postMessage({ command: 'fileListError', error });
            vscode.window.showErrorMessage(error);
            return;
        }

        const targetFolder = selectedFolder === 'workspace' ? workspaceFolder.uri.fsPath : selectedFolder;
        const scriptPath = path.join(this.context.extensionPath, "scripts", "file_lister.py");

        try {
            // Use system Python
            const pythonCmd = this.getSystemPythonCommand();
            
            const env = { 
                ...process.env, 
                VSCODE_WORKSPACE: targetFolder,
                OUTPUT_FORMAT: format,
                INCLUDE_HIDDEN: includeHidden ? "true" : "false"
            };

            await new Promise<void>((resolve, reject) => {
                exec(`"${pythonCmd}" "${scriptPath}"`, { env }, (err, stdout, stderr) => {
                    if (err) {
                        console.error('Python error:', stderr);
                        reject(stderr || err.message);
                    } else {
                        console.log('Python output:', stdout);
                        const outputMatch = stdout.match(/saved to (.+)/);
                        const filePath = outputMatch ? outputMatch[1] : workspaceFolder.uri.fsPath;
                        
                        this._view?.webview.postMessage({ 
                            command: 'fileListSuccess', 
                            filePath: filePath.trim()
                        });
                        vscode.window.showInformationMessage("File list generated successfully!");
                        resolve();
                    }
                });
            });

        } catch (error) {
            const errorMsg = `Error generating file list: ${error}`;
            console.error('Full error:', errorMsg);
            this._view?.webview.postMessage({ command: 'fileListError', error: errorMsg });
            vscode.window.showErrorMessage(errorMsg);
        }
    }

    private async createVectorDatabase(selectedFolder: string, fileTypes: string[], chunkSize: number) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            const error = "No workspace folder open!";
            this._view?.webview.postMessage({ command: 'vectorDbError', error });
            vscode.window.showErrorMessage(error);
            return;
        }

        const targetFolder = selectedFolder === 'workspace' ? workspaceFolder.uri.fsPath : selectedFolder;
        const scriptPath = path.join(this.context.extensionPath, "scripts", "vector_processor.py");

        try {
            // Use system Python
            const pythonCmd = this.getSystemPythonCommand();

            const env = { 
                ...process.env, 
                VSCODE_WORKSPACE: targetFolder,
                FILE_TYPES: fileTypes.join(','),
                CHUNK_SIZE: chunkSize.toString()
            };

            await new Promise<void>((resolve, reject) => {
                const process = exec(`"${pythonCmd}" "${scriptPath}"`, { env });
                
                process.stdout?.on('data', (data) => {
                    console.log('Vector processor output:', data);
                    const progressMatch = data.toString().match(/PROGRESS:(\d+):(.+)/);
                    if (progressMatch) {
                        const progress = parseInt(progressMatch[1]);
                        const message = progressMatch[2];
                        this._view?.webview.postMessage({ 
                            command: 'vectorDbProgress',
                            progress: progress,
                            message: message
                        });
                    }
                });
                
                process.stderr?.on('data', (data) => {
                    console.error('Vector processor error:', data);
                });
                
                process.on('close', (code) => {
                    if (code === 0) {
                        this._view?.webview.postMessage({ command: 'vectorDbSuccess' });
                        vscode.window.showInformationMessage("Vector database created successfully!");
                        resolve();
                    } else {
                        reject(`Process exited with code ${code}`);
                    }
                });
                
                process.on('error', (error) => {
                    reject(error.message);
                });
            });

        } catch (error) {
            const errorMsg = `Error creating vector database: ${error}`;
            this._view?.webview.postMessage({ command: 'vectorDbError', error: errorMsg });
            vscode.window.showErrorMessage(errorMsg);
        }
    }

    private async semanticSearch(query: string, resultCount: number, fileTypeFilter: string) {
        const scriptPath = path.join(this.context.extensionPath, "scripts", "search_tool.py");

        try {
            // Use system Python
            const pythonCmd = this.getSystemPythonCommand();

            const env = { 
                ...process.env, 
                SEARCH_QUERY: query,
                RESULT_COUNT: resultCount.toString(),
                FILE_TYPE_FILTER: fileTypeFilter
            };

            await new Promise<void>((resolve, reject) => {
                exec(`"${pythonCmd}" "${scriptPath}"`, { env }, (err, stdout, stderr) => {
                    if (err) {
                        console.error('Search error:', stderr);
                        reject(stderr || err.message);
                    } else {
                        try {
                            const results = JSON.parse(stdout);
                            this._view?.webview.postMessage({ 
                                command: 'searchResults', 
                                results: results
                            });
                            resolve();
                        } catch (parseError) {
                            reject('Failed to parse search results');
                        }
                    }
                });
            });

        } catch (error) {
            const errorMsg = `Error performing search: ${error}`;
            this._view?.webview.postMessage({ command: 'searchError', error: errorMsg });
            vscode.window.showErrorMessage(errorMsg);
        }
    }

    private async openOutputFolder() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
        if (workspaceFolder) {
            vscode.env.openExternal(vscode.Uri.file(workspaceFolder));
        }
    }

    private async openFile(filePath: string) {
        try {
            // If it's a full path from search results
            if (path.isAbsolute(filePath)) {
                const document = await vscode.workspace.openTextDocument(filePath);
                await vscode.window.showTextDocument(document);
            } else {
                // If it's a relative path from file listing
                const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
                if (workspaceFolder) {
                    const fullPath = path.join(workspaceFolder.uri.fsPath, filePath);
                    const document = await vscode.workspace.openTextDocument(fullPath);
                    await vscode.window.showTextDocument(document);
                }
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Could not open file: ${filePath}`);
        }
    }

    // Comments functionality
    private async sendCurrentFileComments() {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            this._view?.webview.postMessage({ 
                command: 'currentFileComments',
                file: '',
                comments: []
            });
            return;
        }

        const filePath = editor.document.uri.fsPath;
        const comments = await this.getCommentsForFile(filePath);
        
        this._view?.webview.postMessage({ 
            command: 'currentFileComments',
            file: path.basename(filePath),
            comments: comments
        });
    }

    private async getCommentsForFile(filePath: string): Promise<Comment[]> {
        const helpFilePath = this.getHelpFilePath(filePath);
        
        try {
            if (fs.existsSync(helpFilePath)) {
                const content = await fs.promises.readFile(helpFilePath, 'utf-8');
                const data = JSON.parse(content);
                return data.comments || [];
            }
        } catch (error) {
            console.error('Error reading comments file:', error);
        }
        
        return [];
    }

    private getHelpFilePath(filePath: string): string {
        const dir = path.dirname(filePath);
        const baseName = path.basename(filePath, path.extname(filePath));
        const ext = path.extname(filePath).substring(1); // Remove the dot
        return path.join(dir, `${baseName}_${ext}_help.json`);
    }

    private async addComment(type: string, message: string, diff?: string) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active file to comment on');
            return;
        }

        const filePath = editor.document.uri.fsPath;
        const helpFilePath = this.getHelpFilePath(filePath);
        
        try {
            let comments: Comment[] = [];
            
            // Read existing comments
            if (fs.existsSync(helpFilePath)) {
                const content = await fs.promises.readFile(helpFilePath, 'utf-8');
                const data = JSON.parse(content);
                comments = data.comments || [];
            }
            
            // Add new comment
            const newComment: Comment = {
                id: comments.length > 0 ? Math.max(...comments.map(c => c.id)) + 1 : 1,
                username: this.getCurrentUsername(),
                timestamp: new Date().toISOString(),
                type: type as any,
                message: message,
                diff: diff,
                status: 'pending'
            };
            
            comments.unshift(newComment);
            
            // Write back to file
            await fs.promises.writeFile(
                helpFilePath, 
                JSON.stringify({ comments }, null, 2),
                'utf-8'
            );
            
            this._view?.webview.postMessage({ command: 'commentAdded' });
            vscode.window.showInformationMessage('Comment added successfully!');
            
            // Refresh the comments display
            await this.sendCurrentFileComments();
            
        } catch (error) {
            vscode.window.showErrorMessage(`Error adding comment: ${error}`);
        }
    }

    private async applySolution(commentId: number) {
        const editor = vscode.window.activeTextEditor;
        if (!editor) {
            vscode.window.showErrorMessage('No active file to apply solution to');
            return;
        }

        const filePath = editor.document.uri.fsPath;
        const helpFilePath = this.getHelpFilePath(filePath);
        
        try {
            // Read comments to find the solution
            if (!fs.existsSync(helpFilePath)) {
                vscode.window.showErrorMessage('No comments file found');
                return;
            }

            const content = await fs.promises.readFile(helpFilePath, 'utf-8');
            const data = JSON.parse(content);
            const comments: Comment[] = data.comments || [];
            
            const solution = comments.find(c => c.id === commentId && c.type === 'solution');
            if (!solution) {
                vscode.window.showErrorMessage('Solution not found');
                return;
            }

            if (!solution.diff) {
                vscode.window.showErrorMessage('No diff found in solution');
                return;
            }

            // Apply the diff
            await this.applyDiffToFile(filePath, solution.diff);
            
            // Update comment status
            const updatedComments = comments.map(c => 
                c.id === commentId ? { ...c, status: 'applied' as const } : c
            );
            
            await fs.promises.writeFile(
                helpFilePath,
                JSON.stringify({ comments: updatedComments }, null, 2),
                'utf-8'
            );

            this._view?.webview.postMessage({ command: 'solutionApplied' });
            vscode.window.showInformationMessage('Solution applied successfully!');

            // Refresh the comments display
            await this.sendCurrentFileComments();

        } catch (error) {
            vscode.window.showErrorMessage(`Error applying solution: ${error}`);
        }
    }

    private async applyDiffToFile(filePath: string, diffText: string): Promise<void> {
        const document = await vscode.workspace.openTextDocument(filePath);
        const originalText = document.getText();
        
        // Simple diff application (you can enhance this with proper diff parsing)
        const lines = diffText.split('\n');
        const newLines: string[] = [];
        let i = 0;

        while (i < lines.length) {
            const line = lines[i];
            if (line.startsWith('+') && !line.startsWith('+++')) {
                newLines.push(line.substring(1));
            } else if (line.startsWith(' ') || line.startsWith('-')) {
                // Skip context and deletion lines for now
                // In a real implementation, you'd parse the diff properly
            }
            i++;
        }

        // For now, just append the new lines (simplified)
        const newText = originalText + '\n' + newLines.join('\n');
        
        const edit = new vscode.WorkspaceEdit();
        const entireRange = new vscode.Range(
            document.positionAt(0),
            document.positionAt(originalText.length)
        );
        
        edit.replace(document.uri, entireRange, newText);
        await vscode.workspace.applyEdit(edit);
    }

    private getCurrentUsername(): string {
        // In a real implementation, get from Git config or system
        return process.env.USER || process.env.USERNAME || 'anonymous';
    }

    private getSystemPythonCommand(): string {
        return platform() === "win32" ? "python" : "python3";
    }

    public async addCommentToCurrentFile() {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            // Switch to comments tab and focus the comment input
            this._view?.webview.postMessage({ command: 'switchToComments' });
        } else {
            vscode.window.showErrorMessage('No active file to comment on');
        }
    }

    public async applySolutionFromCurrentFile() {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            // This would need to be more sophisticated to select which solution
            vscode.window.showInformationMessage('Use the Comments tab to apply solutions');
        }
    }

    private getNonce(): string {
        return Math.random().toString(36).substring(2, 15);
    }

    dispose() {
        this._disposables.forEach(d => d.dispose());
    }
}
EOL

# Create the CLI tool for git comments
cat <<'EOL' > scripts/git_comment_cli.js
#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

class GitCommentCLI {
    constructor() {
        this.args = process.argv.slice(2);
    }

    run() {
        try {
            const messageIndex = this.args.findIndex(arg => arg === '-m');
            if (messageIndex === -1 || messageIndex === this.args.length - 1) {
                this.showHelp();
                return;
            }

            const message = this.args[messageIndex + 1];
            const filePath = this.args[this.args.length - 1];

            if (!filePath || !fs.existsSync(filePath)) {
                console.error('Error: File path does not exist');
                process.exit(1);
            }

            this.addComment(filePath, message);
            console.log(`Comment added to ${filePath}`);

        } catch (error) {
            console.error('Error:', error.message);
            process.exit(1);
        }
    }

    addComment(filePath, message) {
        const helpFilePath = this.getHelpFilePath(filePath);
        let comments = [];

        // Read existing comments
        if (fs.existsSync(helpFilePath)) {
            const content = fs.readFileSync(helpFilePath, 'utf-8');
            const data = JSON.parse(content);
            comments = data.comments || [];
        }

        // Add new comment
        const newComment = {
            id: comments.length > 0 ? Math.max(...comments.map(c => c.id)) + 1 : 1,
            username: this.getCurrentGitUser(),
            timestamp: new Date().toISOString(),
            type: 'request',
            message: message,
            status: 'pending'
        };

        comments.unshift(newComment);

        // Write back to file
        fs.writeFileSync(
            helpFilePath,
            JSON.stringify({ comments }, null, 2),
            'utf-8'
        );
    }

    getHelpFilePath(filePath) {
        const dir = path.dirname(filePath);
        const baseName = path.basename(filePath, path.extname(filePath));
        const ext = path.extname(filePath).substring(1);
        return path.join(dir, `${baseName}_${ext}_help.json`);
    }

    getCurrentGitUser() {
        try {
            return execSync('git config user.name', { encoding: 'utf-8' }).trim();
        } catch {
            return process.env.USER || process.env.USERNAME || 'anonymous';
        }
    }

    showHelp() {
        console.log(`
Usage: git comment -m "message" <file_path>

Examples:
  git comment -m "Need help with this function" src/main.c
  git comment -m "Here's a solution with diff" --diff player_model.c

Options:
  -m <message>    The comment message (required)
  --diff          Include a diff in the comment (future feature)

This creates/updates a _help.json file alongside the source file with your comment.
        `);
    }
}

// Run the CLI
const cli = new GitCommentCLI();
cli.run();
EOL


# Create the enhanced Python file lister script
cat <<'EOL' > scripts/file_lister.py
import os
import math
import json
import xml.etree.ElementTree as ET
import csv
from xml.dom import minidom

def get_file_info(root_folder, include_hidden=True):
    file_info = []

    def add_folder_contents(folder_path, parent_name):
        # Retrieve contents of the folder
        for root, dirs, files in os.walk(folder_path):
            # Filter directories and files based on hidden preference
            if not include_hidden:
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files[:] = [f for f in files if not f.startswith('.')]
            else:
                # Still skip system directories
                dirs[:] = [d for d in dirs if not (d.startswith('myenv') or d == '__pycache__' or d == 'node_modules' or d == '.git')]

            # Add directories
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                relative_path = os.path.relpath(dir_path, root_folder)
                folder_name = os.path.basename(dir_path)
                if parent_name:  # Append to the parent
                    file_info.append([f"{parent_name}/{folder_name}", "Folder", ""])
                else:  # Root level folders
                    file_info.append([folder_name, "Folder", ""])
                add_folder_contents(dir_path, f"{parent_name}/{folder_name}" if parent_name else folder_name)

            # Add files
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    file_size = os.path.getsize(file_path)
                    file_type = file_name.split('.')[-1].lower() if '.' in file_name else "File"
                    relative_path = os.path.relpath(file_path, root_folder)
                    size_str = format_size(file_size)
                    file_info.append([relative_path, file_type, size_str])
                except (OSError, IOError):
                    # Skip files that can't be accessed
                    continue
            break  # Avoid descending into subfolders again

    add_folder_contents(root_folder, "")
    
    return file_info

def format_size(size):
    if not isinstance(size, (int, float)):
        return ""  # For non-numeric sizes
    
    if size == 0:
        return "0 B"
    
    size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
    i = int(math.floor(math.log(size, 1024)))
    p = math.pow(1024, i)
    s = round(size / p, 2)
    return f"{s} {size_name[i]}"

def save_to_json(file_info, output_file):
    # Save as regular JSON format (list of lists)
    json_data = [{"Name": item[0], "Type": item[1], "Size": item[2]} for item in file_info]
    with open(output_file, 'w') as json_file:
        json.dump(json_data, json_file, indent=4)

def save_ai_format_json(file_info, output_file):
    # Save as AI training format (dict with file names as keys)
    ai_data = {item[0]: {"Type": item[1], "Size": item[2]} for item in file_info}
    with open(output_file, 'w') as json_file:
        json.dump(ai_data, json_file, indent=4)

def save_to_txt(file_info, output_file):
    # Save as readable text format
    with open(output_file, 'w') as txt_file:
        txt_file.write("File List\n")
        txt_file.write("=========\n\n")
        for item in file_info:
            name, file_type, size = item
            if file_type == "Folder":
                txt_file.write(f"[FOLDER] {name}/\n")
            else:
                txt_file.write(f"[{file_type.upper():<6}] {name} ({size})\n")

def save_to_xml(file_info, output_file):
    # Save as XML format
    root = ET.Element("FileList")
    for item in file_info:
        file_elem = ET.SubElement(root, "File" if item[1] != "Folder" else "Folder")
        file_elem.set("name", item[0])
        file_elem.set("type", item[1])
        if item[2]:  # Size (empty for folders)
            file_elem.set("size", item[2])
    
    # Pretty print XML
    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open(output_file, 'w') as xml_file:
        xml_file.write(xml_str)

def save_to_csv(file_info, output_file):
    # Save as CSV format
    with open(output_file, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['Name', 'Type', 'Size'])
        for item in file_info:
            writer.writerow(item)

if __name__ == "__main__":
    # Get workspace folder from environment variable
    root_folder = os.environ.get("VSCODE_WORKSPACE", os.getcwd())
    output_format = os.environ.get("OUTPUT_FORMAT", "json")
    include_hidden = os.environ.get("INCLUDE_HIDDEN", "true").lower() == "true"
    
    folder_name = os.path.basename(root_folder.rstrip('/'))  # Get the current folder name

    # Define output files based on format
    output_files = {
        "json": f"{folder_name}_file_info.json",
        "ai_json": f"{folder_name}_file_info_ai_format.json", 
        "txt": f"{folder_name}_file_info.txt",
        "xml": f"{folder_name}_file_info.xml",
        "csv": f"{folder_name}_file_info.csv"
    }
    
    output_file = output_files.get(output_format, output_files["json"])
    output_path = os.path.join(root_folder, output_file)

    try:
        # Get file information
        file_info = get_file_info(root_folder, include_hidden)

        # Save the file information in the requested format
        if output_format == "json":
            save_to_json(file_info, output_path)
        elif output_format == "ai_json":
            save_ai_format_json(file_info, output_path)
        elif output_format == "txt":
            save_to_txt(file_info, output_path)
        elif output_format == "xml":
            save_to_xml(file_info, output_path)
        elif output_format == "csv":
            save_to_csv(file_info, output_path)

        print(f"File information saved to {output_path}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
EOL

# Create the vector processor
cat <<'EOL' > scripts/vector_processor.py
import os
import json
import chromadb
from sentence_transformers import SentenceTransformer
import tiktoken
from pathlib import Path
import sys

class CodebaseVectorizer:
    def __init__(self, persist_directory="./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection("codebase")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def smart_chunk_text(self, text, max_tokens=512):
        """Split text into semantic chunks"""
        sentences = text.split('. ')
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            test_chunk = current_chunk + ". " + sentence if current_chunk else sentence
            if len(self.tokenizer.encode(test_chunk)) <= max_tokens:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
                
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
    
    def chunk_code_file(self, content, file_ext):
        """Smart chunking for code files"""
        chunks = []
        
        if file_ext in ['py']:
            # Chunk by functions and classes for Python
            lines = content.split('\n')
            current_chunk = []
            in_function = False
            
            for line in lines:
                if line.strip().startswith('def ') or line.strip().startswith('class '):
                    if current_chunk:
                        chunks.append('\n'.join(current_chunk))
                        current_chunk = []
                current_chunk.append(line)
                
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                
        elif file_ext in ['js', 'ts', 'java', 'cpp']:
            # Chunk by functions and classes for other languages
            chunks = self.smart_chunk_text(content)
        else:
            # For other files, use generic text chunking
            chunks = self.smart_chunk_text(content)
            
        return [chunk for chunk in chunks if chunk.strip()]
    
    def process_file(self, file_path, metadata, chunk_size=512):
        """Process a single file and add to vector DB"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            if not content.strip():
                return 0
                
            file_ext = metadata['type']
            
            if file_ext in ['py', 'js', 'ts', 'java', 'cpp', 'c', 'rb', 'php', 'go']:
                chunks = self.chunk_code_file(content, file_ext)
            else:
                chunks = self.smart_chunk_text(content, chunk_size)
            
            if not chunks:
                return 0
                
            # Generate embeddings for each chunk
            embeddings = self.encoder.encode(chunks)
            
            # Prepare documents for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc_id = f"{file_path}_{i}"
                documents.append(chunk)
                metadatas.append({
                    'file_path': file_path,
                    'file_type': file_ext,
                    'file_size': metadata['size'],
                    'chunk_index': i,
                    'total_chunks': len(chunks)
                })
                ids.append(doc_id)
            
            # Add to ChromaDB
            self.collection.add(
                embeddings=embeddings.tolist(),
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            return len(chunks)
            
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            return 0
    
    def process_file_manifest(self, manifest_path, root_directory, file_types, chunk_size=512):
        """Process all files from file manifest"""
        with open(manifest_path, 'r') as f:
            file_manifest = json.load(f)
        
        total_chunks = 0
        processed_files = 0
        total_files = len([f for f in file_manifest.items() if f[1]['Type'] != 'Folder' and f[1]['Type'] in file_types])
        
        for file_path, metadata in file_manifest.items():
            full_path = os.path.join(root_directory, file_path)
            
            # Skip directories and non-existent files
            if metadata['Type'] == 'Folder' or not os.path.exists(full_path):
                continue
                
            # Only process selected file types
            file_ext = metadata['Type'].lower()
            if file_ext in file_types:
                chunks_added = self.process_file(full_path, {
                    'type': file_ext,
                    'size': metadata['Size']
                }, chunk_size)
                total_chunks += chunks_added
                processed_files += 1
                
                # Report progress
                progress = int((processed_files / total_files) * 100)
                print(f"PROGRESS:{progress}:Processed {processed_files}/{total_files} files, {total_chunks} chunks...")
        
        print(f"PROGRESS:100:Complete! Processed {processed_files} files into {total_chunks} chunks")

if __name__ == "__main__":
    root_folder = os.environ.get("VSCODE_WORKSPACE", os.getcwd())
    file_types = os.environ.get("FILE_TYPES", "py,js,ts,md").split(',')
    chunk_size = int(os.environ.get("CHUNK_SIZE", "512"))
    
    # First generate file manifest
    manifest_script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'file_lister.py')
    
    # Run file lister to generate manifest
    import subprocess
    env = os.environ.copy()
    env['VSCODE_WORKSPACE'] = root_folder
    env['OUTPUT_FORMAT'] = 'ai_json'
    env['INCLUDE_HIDDEN'] = 'false'
    
    result = subprocess.run([
        sys.executable, manifest_script
    ], env=env, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error generating file manifest: {result.stderr}")
        exit(1)
    
    # Find the generated manifest file
    folder_name = os.path.basename(root_folder.rstrip('/'))
    manifest_path = os.path.join(root_folder, f"{folder_name}_file_info_ai_format.json")
    
    if not os.path.exists(manifest_path):
        print(f"Manifest file not found: {manifest_path}")
        exit(1)
    
    # Initialize and process
    vectorizer = CodebaseVectorizer()
    vectorizer.process_file_manifest(manifest_path, root_folder, file_types, chunk_size)
EOL

# Create the search tool
cat <<'EOL' > scripts/search_tool.py
import os
import json
import chromadb
from sentence_transformers import SentenceTransformer

class CodebaseSearch:
    def __init__(self, db_path="./chroma_db"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_collection("codebase")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
    
    def search(self, query, n_results=10, file_type_filter=None):
        """Search the vector database"""
        query_embedding = self.encoder.encode([query]).tolist()
        
        where = None
        if file_type_filter:
            where = {"file_type": file_type_filter}
        
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where
        )
        
        # Format results for JSON output
        formatted_results = []
        for i in range(len(results['documents'][0])):
            formatted_results.append({
                'file': results['metadatas'][0][i]['file_path'],
                'content': results['documents'][0][i],
                'score': 1 - results['distances'][0][i],  # Convert distance to similarity score
                'type': results['metadatas'][0][i]['file_type'],
                'chunk': results['metadatas'][0][i]['chunk_index'] + 1
            })
        
        return formatted_results

if __name__ == "__main__":
    query = os.environ.get("SEARCH_QUERY", "")
    result_count = int(os.environ.get("RESULT_COUNT", "10"))
    file_type_filter = os.environ.get("FILE_TYPE_FILTER", "")
    
    if not query:
        print("[]")
        exit(0)
    
    try:
        search = CodebaseSearch()
        results = search.search(query, result_count, file_type_filter if file_type_filter else None)
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"[]")
        # print(f"Error during search: {str(e)}", file=sys.stderr)
EOL

# Create enhanced requirements.txt
cat <<EOL > requirements.txt
# File listing and processing
pandas
cairosvg

# Vector database and embeddings
chromadb
sentence-transformers
tiktoken

# Additional utilities
numpy
requests
EOL


# Create README.md
cat <<EOL > README.md
# Code Collaborator VS Code Extension

## 🚀 Features

### File Analysis
- **Multiple output formats**: JSON, AI JSON, TXT, XML, CSV
- **Folder selection**: Scan entire workspace or specific folders
- **Smart filtering**: Automatically skips system directories

### Vector Database
- **Semantic embeddings**: Convert code to vector representations
- **Smart chunking**: Intelligent code splitting by functions/classes
- **File type filtering**: Process only specific file types
- **Progress tracking**: Real-time progress updates

### Semantic Search
- **Natural language queries**: Search code with plain English
- **Relevance scoring**: Results ranked by semantic similarity
- **File type filtering**: Filter results by programming language
- **Quick navigation**: Click results to open files in editor

### Code Comments (NEW!)
- **Git-integrated comments**: Collaborative help system
- **One-click apply**: Apply solutions directly from comments
- **Diff support**: Include code changes in solutions
- **Context-aware**: Comments tied to specific files

## 🛠️ Installation

1. Run the installation script:
\`\`\`bash
./install.sh
\`\`\`

2. Open VS Code and look for the "Code Collaborator" icon in the activity bar

## 💬 Using Git Comments

### VS Code Extension:
1. Open any source file
2. Click the "Code Collaborator" icon
3. Go to the "Code Comments" tab
4. Add help requests, solutions, or feedback
5. Click "Apply Solution" to apply diffs directly

### Command Line:
\`\`\`bash
git comment -m "Need help with shadows" src/player_model.c
git comment -m "Here's a solution" --diff src/player_model.c
\`\`\`

## 🔧 Setup Git Alias (Optional)

Add this to your \`~/.gitconfig\`:
\`\`\`ini
[alias]
    comment = "!node /path/to/codecollaborator/scripts/git_comment_cli.js"
\`\`\`

## 📁 File Structure

\`\`\`
codecollaborator/
├── src/                 # TypeScript source
├── scripts/            # Python scripts and CLI
├── resources/          # Icons and assets
├── out/               # Compiled JavaScript
└── *.json             # Configuration files
\`\`\`

## 🎯 Perfect For

- **Large codebases** analysis
- **AI training data** preparation
- **Team collaboration** on code issues
- **Knowledge sharing** through executable solutions
- **Code search** and discovery

## ⚡ Performance

- **Fast processing**: Optimized for large projects
- **Smart memory management**: Handles 200K+ files efficiently
- **Real-time search**: Millisecond query response times
- **Git-native**: Works with your existing workflow
EOL

# Create LICENSE.md
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

# Create the main installation script
cat <<'EOL' > install.sh
#!/bin/bash

echo "🚀 Installing Code Collaborator..."

# Check if we're in the extension directory
if [ ! -f "package.json" ]; then
    echo "Error: Please run this script from the codecollaborator directory"
    exit 1
fi

# Node & TypeScript Setup
echo "📦 Setting up Node.js dependencies..."
export NODE_OPTIONS=--openssl-legacy-provider

if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
fi

# Install TypeScript if needed
if ! command -v tsc &> /dev/null; then
    npm install -g typescript
fi

# Compile TypeScript
echo "🔨 Compiling TypeScript..."
npm run compile

# Python Environment
echo "🐍 Setting up Python environment..."
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "Error: Python is required but not installed"
    exit 1
fi

# Create virtual environment
python3 -m venv myenv 2>/dev/null || python -m venv myenv

# Activate virtual environment and install requirements
if [ -f "myenv/bin/activate" ]; then
    source myenv/bin/activate
elif [ -f "myenv/Scripts/activate" ]; then
    source myenv/Scripts/activate
fi

pip install --upgrade pip
pip install -r requirements.txt

# Make CLI executable
chmod +x scripts/git_comment_cli.js

# Package extension
echo "📦 Packaging extension..."
if command -v vsce &> /dev/null; then
    vsce package --allow-missing-repository
    VSIX_FILE="codecollaborator-1.0.0.vsix"
    
    if [ -f "$VSIX_FILE" ]; then
        echo "✅ Extension packaged: $VSIX_FILE"
        
        # Install in VS Code
        if command -v code &> /dev/null; then
            echo "🔧 Installing extension in VS Code..."
            code --install-extension "$VSIX_FILE" --force
            echo "✅ Code Collaborator installed successfully!"
        else
            echo "📦 Extension packaged but 'code' command not found."
            echo "   Install manually from: $VSIX_FILE"
        fi
    else
        echo "❌ Failed to package extension"
    fi
else
    echo "⚠️  VSCE not installed. Install with: npm install -g vsce"
    echo "   Then run: vsce package --allow-missing-repository"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "To use Code Collaborator:"
echo "1. Open a workspace in VS Code"
echo "2. Look for the Code Collaborator icon in the activity bar"
echo "3. Use the four tabs:"
echo "   - File Lister: Generate file manifests"
echo "   - Vector Database: Create semantic search index"
echo "   - Semantic Search: Find code with natural language"
echo "   - Code Comments: Collaborative help with one-click apply"
echo ""
echo "For Git comments CLI:"
echo "  git comment -m 'your message' path/to/file.c"
echo ""
echo "Enjoy! 🚀"
EOL

chmod +x install.sh

# Create .vscodeignore
cat <<EOL > .vscodeignore
node_modules
.vscode
*.ts
*.map
.git
.gitignore
README.md
src/
tsconfig.json
package-lock.json
myenv/
install.sh
EOL

echo "✅ Ultimate Code Collaborator created in '$EXTNAME'!"
echo ""
echo "🚀 To install and use:"
echo "   cd $EXTNAME && ./install.sh"
echo ""
echo "The extension includes:"
echo "✓ File analysis with multiple formats"
echo "✓ Vector database for semantic search"  
echo "✓ Natural language code search"
echo "✓ Git-integrated code comments"
echo "✓ One-click solution application"
echo "✓ CLI tool for git comments"
echo ""
echo "🎯 Perfect for team collaboration and large codebases!"


# Continue with build and installation...
echo "Building and installing the extension..."

# Node & TypeScript Setup
export NODE_OPTIONS=--openssl-legacy-provider
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

echo "Node version: $(node -v)"
echo "npm version: $(npm -v)"

# Install npm dependencies
if [ ! -d "node_modules" ]; then
    echo "Installing Node dependencies..."
    npm install
fi

npm install --save-dev typescript

# Compile TypeScript
echo "Compiling TypeScript..."
npm run compile

# Python Environment
python3 -m venv myenv
source myenv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Convert SVG to PNG
if command -v cairosvg &> /dev/null; then
    python -m cairosvg resources/logo.svg -o resources/logo.png
else
    echo "Note: Install cairosvg for better logo support: pip install cairosvg"
fi

# Package extension
if command -v vsce &> /dev/null; then
    echo "Packaging extension..."
    vsce package --allow-missing-repository
    VSIX_FILE="${EXTNAME}-1.0.0.vsix"
    
    if [ -f "$VSIX_FILE" ]; then
        echo "✅ Extension packaged: $VSIX_FILE"
        
        if command -v code &> /dev/null; then
            echo "Installing extension in VS Code..."
            code --install-extension "$VSIX_FILE" --force
            echo "✅ Advanced File Analyzer installed! Reload VS Code to see it in the activity bar."
        fi
    else
        echo "❌ Failed to package extension."
    fi
else
    echo "Note: Install vsce to package extension: npm install -g vsce"
fi

echo ""
echo "🎉 Advanced File Analyzer extension created successfully!"
echo "📁 Location: $(pwd)"
echo ""
echo "To use the extension:"
echo "1. Open a workspace folder in VS Code"
echo "2. Look for the File Analyzer icon in the activity bar"
echo "3. Use the three tabs:"
echo "   - File Lister: Generate file manifests"
echo "   - Vector Database: Create semantic search index"  
echo "   - Semantic Search: Find code with natural language"
echo ""
echo "Perfect for large codebases and AI training data preparation!"


# ========== GLOBAL GIT ALIAS INSTALLATION ==========
echo "🔧 Installing global Git alias..."
CURRENT_DIR=$(pwd)
CLI_SCRIPT="$CURRENT_DIR/scripts/git_comment_cli.js"

# Check if CLI script exists
if [ -f "$CLI_SCRIPT" ]; then
    # Make sure it's executable
    chmod +x "$CLI_SCRIPT"
    
    # Set global Git alias
    git config --global alias.comment "!node $CLI_SCRIPT"
    
    # Verify the alias was set
    if git config --global --get alias.comment > /dev/null; then
        echo "✅ Global Git alias 'comment' installed successfully!"
        echo "   You can now use: git comment -m 'your message' file.py"
    else
        echo "⚠️  Git alias installation may have failed"
    fi
else
    echo "❌ CLI script not found at: $CLI_SCRIPT"
    echo "   Git alias not installed"
fi

# ========== CREATE GLOBAL WRAPPER SCRIPT (Backup) ==========
echo "📝 Creating global wrapper script as backup..."
mkdir -p ~/.local/bin

# Create a wrapper script that can find the extension directory
cat > ~/.local/bin/git-comment << 'EOF'
#!/bin/bash
# Find codecollaborator extension directory dynamically
EXTENSION_DIR=$(find ~ -name "codecollaborator" -type d 2>/dev/null | head -1)

if [ -z "$EXTENSION_DIR" ]; then
    echo "Error: Could not find codecollaborator extension directory"
    echo "Make sure the extension is installed in your home directory"
    exit 1
fi

CLI_SCRIPT="$EXTENSION_DIR/scripts/git_comment_cli.js"

if [ ! -f "$CLI_SCRIPT" ]; then
    echo "Error: CLI script not found at $CLI_SCRIPT"
    exit 1
fi

node "$CLI_SCRIPT" "$@"
EOF

# Make wrapper executable
chmod +x ~/.local/bin/git-comment

# Add to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
    echo "✅ Added ~/.local/bin to PATH in ~/.zshrc"
    echo "   Run: source ~/.zshrc or restart your terminal"
fi

echo "✅ Global wrapper script created at: ~/.local/bin/git-comment"

# ========== VERIFICATION ==========
echo "🔍 Verifying installation..."
echo "Git alias status:"
git config --global --get alias.comment

echo ""
echo "🎉 Installation complete!"
echo ""
echo "To use Code Collaborator:"
echo "1. Open a workspace in VS Code"
echo "2. Look for the Code Collaborator icon in the activity bar"
echo "3. Use the four tabs:"
echo "   - File Lister: Generate file manifests"
echo "   - Vector Database: Create semantic search index"
echo "   - Semantic Search: Find code with natural language"
echo "   - Code Comments: Collaborative help with one-click apply"
echo ""
echo "For Git comments CLI:"
echo "  git comment -m 'your message' path/to/file.c"
echo ""
echo "If git comment doesn't work, use:"
echo "  git-comment -m 'your message' path/to/file.c"
echo ""
echo "Enjoy! 🚀"