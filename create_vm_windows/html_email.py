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
    
    # Extract YouTube video ID from URL
    def get_youtube_video_id(url):
        import re
        regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|v\/|live\/|.+\?v=)?|youtu\.be\/)([^&\n?#]+)"
        match = re.search(regex, url)
        return match.group(1) if match else None
    
    video_id = get_youtube_video_id(youtube_embed_src)
    youtube_embed_url = f"https://www.youtube.com/embed/{video_id}?loop=1&mute=1&playlist={video_id}" if video_id else ""
    
    # Format IPv6 style address for iOS
    ios_address = f"[::ffff:{ip_address}]"
    
    # Create pin URL - use the direct URL without tracking
    pin_url = f"https://{ip_address}:47990/pin"
    
    # Create drop URL - use the direct URL without tracking
    drop_url = f"https://{ip_address}:3475"

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
            background: rgba(30, 30, 30, 0.95); /* Increased opacity to reduce dark overlay effect */
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
        }}

        .code-content {{
            padding-right: 15px;
            overflow: auto;
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
    </style>
</head>

<body>
    <div class="container">
        <div class="header">
            <img src="{logo_src}" alt="Logo" />
            <h1>{main_heading}</h1>
            <div class="description">{main_description}</div>
        </div>

        <iframe src="{youtube_embed_url}" allowfullscreen></iframe>

        <div class="section">
            <div class="section-title"><i>🔗</i> Open <strong>Moonlight</strong> and Add:</div>
            <div class="code-box">
                <div class="code-content">{ip_address}</div>
            </div>

            <div class="section-title"><i>📱</i> Open <strong>iOS Moonlight</strong> and Add:</div>
            <div class="code-box">
                <div class="code-content">{ios_address}</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i>🔒</i> Enter 4-digit PIN here:</div>
            <div class="code-box">
                <div class="code-content">
                    <a href="{pin_url}" target="_blank">{pin_url}</a>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i>👤</i> Use credentials:</div>
            <div class="code-box">
                <div class="code-content">{credentials_sunshine}</div>
            </div>

            <div class="section-title"><i>💻</i> Windows Password:</div>
            <div class="code-box">
                <div class="code-content">{windows_password}</div>
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

         <div class="section">
            <div class="section-title"><i>⬆️</i> Upload files directly:</div>
            <div class="code-box">
                <div class="code-content">
                    <a href="{drop_url}" target="_blank">{drop_url}</a>
                </div>
            </div>
        </div>
        <div class="download-section">
            <div>{form_description}</div>
            <div class="code-box">
                <div class="code-content">
                    <a href="{form_link}" target="_blank">{form_link}</a>
                </div>
            </div>
        </div>

        <iframe src="{discord_widget_src}" width="100%" height="350" allowtransparency="true" frameborder="0"
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
    <img class="company-logo" src="{company_src}"/>
</body>

</html>
"""