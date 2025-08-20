def HTMLEmail(ip_address: str,
              background_image_url: str,
              title: str,
              main_heading: str,
              main_description: str,
              youtube_embed_src: str,
              image_left_src: str,
              image_right_src: str,
              logo_src: str,
              company_src: str,
              discord_widget_src: str,
              windows_password: str,
              credentials_sunshine: str,
              form_description: str,
              form_link: str):
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8" />
    <title>{title}</title>
    <link rel="shortcut icon" href="https://i.ibb.co/kVtMTrWf/nvidia.png" type="image/x-icon">
    <meta name="author" content="win10dev.xyz">
    <meta property="article:published_time" content="2025-04-19T10:00:00Z">
    <meta name="description" content="Your virtual machine is ready to use">
    <meta itemprop="name" content="{title}">
    <meta itemprop="description" content="Your virtual machine is ready to use">
    <meta itemprop="image" content="">
    <meta name="keywords" content="{title}">
    <meta property="og:title" content="{title}">
    <meta property="og:url" content="https://win10dev.xyz">
    <meta property="og:type" content="website">
    <meta property="og:description" content="Your virtual machine is ready to use">
    <meta property="og:image" content="">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="Your virtual machine is ready to use">
    <meta name="twitter:card" content="summary_large_image">
    <style>
        :root {{
            --primary: #0f9d58;
            --primary-dark: #0a7a45;
            --primary-light: #1db954;
            --secondary: #107c10;
            --accent: #00b4d8;
            --accent-alt: #ff6b6b;
            --dark: #0a0a0a;
            --medium: #1a1a1a;
            --light: #f8f9fa;
            --border: rgba(255, 255, 255, 0.1);
            --glow: 0 0 15px rgba(16, 124, 16, 0.7);
            --transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--dark);
            color: var(--light);
            background-image: url('{background_image_url}');
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            background-attachment: fixed;
            line-height: 1.6;
            padding: 15px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 700px;
            margin: 0 auto;
            background: rgba(30, 30, 30, 0.9);
            padding: 25px;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(5px);
            border: 1px solid var(--border);
        }}

        .header {{
            text-align: center;
            margin-bottom: 25px;
        }}

        .header img {{
            max-width: 180px;
            height: auto;
            margin-bottom: 15px;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.05); }}
            100% {{ transform: scale(1); }}
        }}

        h1 {{
            font-size: 2.2rem;
            color: var(--primary);
            margin-bottom: 10px;
            text-shadow: 0 0 10px rgba(16, 124, 16, 0.5);
        }}

        .description {{
            font-size: 1.1rem;
            margin-bottom: 25px;
            background: rgba(42, 42, 42, 0.7);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid var(--primary);
            white-space: pre-wrap;
        }}

        iframe {{
            width: 100%;
            height: 300px;
            border: none;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.4);
        }}

        .section {{
            margin-bottom: 20px;
        }}

        .section-title {{
            font-size: 1.3rem;
            color: var(--accent);
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .section-title i {{
            color: var(--primary);
        }}

        .code-box {{
            background: rgba(42, 42, 42, 0.7);
            padding: 15px;
            border-radius: 10px;
            position: relative;
            margin: 12px 0;
            border: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .code-content {{
            flex-grow: 1;
            padding-right: 15px;
            overflow: auto;
        }}

        .copy-btn {{
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 0.95rem;
            transition: var(--transition);
            flex-shrink: 0;
            min-width: 65px;
            user-select: none;
        }}

        .copy-btn:hover {{
            background: var(--secondary);
            transform: translateY(-2px);
        }}

        .code-box strong {{
            color: var(--accent);
        }}

        a {{
            color: var(--accent);
            text-decoration: none;
            transition: var(--transition);
            word-break: break-word;
        }}

        a:hover {{
            color: #00ffff;
            text-decoration: underline;
        }}

        .download-section {{
            text-align: center;
            margin-top: 35px;
            padding: 20px;
            background: rgba(16, 124, 16, 0.2);
            border-radius: 10px;
            border-top: 2px solid var(--primary);
        }}

        .fixed-images {{
            position: fixed;
            bottom: 15px;
            left: 0;
            right: 0;
            display: flex;
            justify-content: space-between;
            pointer-events: none;
            z-index: 1000;
            padding: 0 15px;
        }}

        .fixed-image-left,
        .fixed-image-right {{
            position: static;
            background-color: transparent;
            margin: 0;
            padding: 0;
        }}


        .fixed-images a {{
            pointer-events: auto;
        }}

        .fixed-images img {{
            width: 70px;
            height: auto;
            opacity: 0.8;
            transition: var(--transition);
        }}

        .fixed-images img:hover {{
            opacity: 1;
            transform: scale(1.05);
        }}

        .company-logo {{
            display: block;
            margin: 25px auto 0;
            max-width: 280px;
            height: auto;
        }}

        #image-left, #image-right {{
            position: fixed;
            bottom: 50px;
            width: 100px;
            z-index: 999;
        }}

        #image-left {{
            left: 0;
        }}

        #image-right {{
            right: 0;
        }}

        /* Responsive adjustments for small screens */
        @media (max-width: 320px) {{
            body {{
                padding: 8px;
                font-size: 16px;
            }}

            .container {{
                padding: 15px 12px;
            }}

            h1 {{
                font-size: 1.7rem;
            }}

            .description {{
                font-size: 1rem;
                padding: 12px;
                margin-bottom: 20px;
            }}

            iframe {{
                height: 180px;
                margin-bottom: 15px;
            }}

            .section-title {{
                font-size: 1.15rem;
                margin-bottom: 10px;
            }}

            .code-box {{
                padding: 12px;
                font-size: 0.9rem;
                flex-direction: column;
                align-items: flex-start;
            }}

            .code-content {{
                padding-right: 0;
                padding-bottom: 10px;
                width: 100%;
            }}

            .copy-btn {{
                align-self: flex-end;
                margin-top: 8px;
                padding: 6px 10px;
                font-size: 0.85rem;
            }}

            .header img {{
                max-width: 140px;
            }}

            .fixed-images img {{
                width: 55px;
            }}

            .company-logo {{
                max-width: 180px;
            }}

            .download-section {{
                margin-top: 25px;
                padding: 15px;
            }}
        }}

        /* Notification for copy success */
        .copy-notification {{
            position: fixed;
            top: 15px;
            right: 15px;
            background: var(--primary);
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
            transform: translateY(-100px);
            transition: transform 0.3s ease;
            z-index: 2000;
            font-size: 1rem;
        }}

        .copy-notification.show {{
            transform: translateY(0);
        }}
    </style>
</head>

<body>
    <div class="container">
        <div class="header">
            <img id="logo" src="{logo_src}" alt="Logo" />
            <h1 id="t_main">{main_heading}</h1>
            <div class="description" id="d_main">{main_description}</div>
        </div>

        <iframe id="y_main" src="" allowfullscreen></iframe>

        <div class="section">
            <div class="section-title"><i>🔗</i> Open <strong>Moonlight</strong> and Add:</div>
            <div class="code-box">
                <div class="code-content" id="ipAddress">0.0.0.0</div>
                <button class="copy-btn" data-target="ipAddress">Copy</button>
            </div>

            <div class="section-title"><i>📱</i> Open <strong>iOS Moonlight</strong> and Add:</div>
            <div class="code-box">
                <div class="code-content" id="iOSAddress">[::ffff:0.0.0.0]</div>
                <button class="copy-btn" data-target="iOSAddress">Copy</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i>🔒</i> Enter 4-digit PIN here:</div>
            <div class="code-box">
                <div class="code-content">
                    <a href="" id="pinLink" target="_blank">https://0.0.0.0:47990/pin</a>
                </div>
                <button class="copy-btn" id="pinCopy">Copy Link</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i>👤</i> Use credentials:</div>
            <div class="code-box">
                <div class="code-content" id="credentials">{credentials_sunshine}</div>
                <button class="copy-btn" data-target="credentials">Copy</button>
            </div>

            <div class="section-title"><i>💻</i> Windows Password:</div>
            <div class="code-box">
                <div class="code-content" id="winPass">{windows_password}</div>
                <button class="copy-btn" data-target="winPass">Copy</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i>⬇️</i> You need to download <strong>Moonlight</strong> to connect:</div>
            <div class="code-box">
                <div class="code-content">
                    <a href="https://github.com/moonlight-stream/moonlight-qt/releases" target="_blank">
                        https://github.com/moonlight-stream/moonlight-qt/releases
                    </a>
                </div>
            </div>
        </div>

        <div class="download-section">
            <div id="formdesc">{form_description}</div>
            <div class="code-box">
                <div class="code-content" id="vhdblock">
                    <a href="{form_link}" id="vhdLink" target="_blank">{form_link}</a>
                </div>
            </div>
        </div>

        <iframe id="discord" src="{discord_widget_src}" width="100%" height="350" allowtransparency="true" frameborder="0"
            sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts"></iframe>
    </div>

    <div class="fixed-images">
        <a href="https://portal.azure.com" target="_blank" class="fixed-image-left">
            <img src="https://i.ibb.co/459vKcy/azure.png" alt="Azure" />
        </a>
        <a href="https://ue3rtx.netlify.app" target="_blank" class="fixed-image-right">
            <img src="https://i.ibb.co/mChg6mrj/nvidiartx.png" alt="NVIDIA RTX" />
        </a>
    </div>

    <img id="image-left" src="{image_left_src}" />
    <img id="image-right" src="{image_right_src}" />
    <br />
    <img class="company-logo" id="company" src="{company_src}"/>

    <div class="copy-notification" id="copyNotification">Copied to clipboard!</div>

    <script>
        function getQueryParam(name) {{
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get(name);
        }}

        function showNotification(message) {{
            const notification = document.getElementById('copyNotification');
            notification.textContent = message;
            notification.classList.add('show');
            setTimeout(() => {{
                notification.classList.remove('show');
            }}, 2000);
        }}

        async function copyToClipboard(text) {{
            try {{
                await navigator.clipboard.writeText(text);
                showNotification('Copied to clipboard!');
                return true;
            }} catch (err) {{
                console.error('Failed to copy: ', err);
                // Fallback for older browsers
                const textarea = document.createElement('textarea');
                textarea.value = text;
                document.body.appendChild(textarea);
                textarea.select();
                const result = document.execCommand('copy');
                document.body.removeChild(textarea);
                if (result) {{
                    showNotification('Copied to clipboard!');
                    return true;
                }} else {{
                    showNotification('Failed to copy');
                    return false;
                }}
            }}
        }}

        function setupEventListeners() {{
            document.addEventListener('click', function (e) {{
                if (e.target && e.target.matches('.copy-btn[data-target]')) {{
                    const targetId = e.target.getAttribute('data-target');
                    const targetElement = document.getElementById(targetId);
                    if (targetElement) {{
                        const text = targetElement.textContent.trim();
                        copyToClipboard(text);
                    }}
                }}

                if (e.target && e.target.id === 'pinCopy') {{
                    const pinLink = document.getElementById('pinLink');
                    copyToClipboard(pinLink.href);
                }}
            }});
        }}

        function updateContent() {{
            const ipAddress = getQueryParam('url') || '{ip_address}';
            const formUrl = getQueryParam('form') || '{form_link}';

            document.getElementById('ipAddress').textContent = ipAddress;
            document.getElementById('iOSAddress').textContent = `[::ffff:${{ipAddress}}]`;

            const pinLink = document.getElementById('pinLink');
            pinLink.href = `https://${{ipAddress}}:47990/pin`;
            pinLink.textContent = `https://${{ipAddress}}:47990/pin`;

            const vhdLink = document.getElementById('vhdLink');
            if (vhdLink) {{
                if (formUrl) {{
                    vhdLink.style.display = 'block';
                    vhdLink.href = formUrl;
                    vhdLink.textContent = formUrl;
                }} else {{
                    vhdLink.style.display = 'none';
                }}
            }}
        }}

        function initializePage() {{
            updateContent();
            setupEventListeners();
            updateYoutubeEmbed("{youtube_embed_src}");
        }}

        function updateYoutubeEmbed(url) {{
            const getYoutubeVideoId = (url) => {{
                const regex = /(?:https?:\\/\\/)?(?:www\\.)?(?:youtube\\.com\\/(?:watch\\?v=|embed\\/|v\\/|live\\/|.+\\?v=)?|youtu\\.be\\/)([^&\\n?#]+)/;
                const match = url.match(regex);
                return match ? match[1] : null;
            }};

            const videoId = getYoutubeVideoId(url);
            if (videoId) {{
                document.getElementById('y_main').src = `https://www.youtube.com/embed/${{videoId}}?loop=1&mute=1&playlist=${{videoId}}`;
            }} else {{
                document.getElementById('y_main').src = ''; // or fallback URL
            }}
        }}

        document.addEventListener('DOMContentLoaded', initializePage);
    </script>
</body>

</html>
"""