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
              form_link: str,
              new_vm_url: str,
              dash_url: str):
    
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
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
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
            color: var(--light);
            line-height: 1.6;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .container {{
            max-width: 800px;
            width: 100%;
            background: rgba(20, 20, 20, 0.92);
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(8px);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }}

        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .header img {{
            max-width: 200px;
            height: auto;
            margin-bottom: 20px;
            filter: drop-shadow(0 0 10px rgba(16, 124, 16, 0.5));
        }}

        h1 {{
            font-size: 2.4rem;
            color: var(--primary);
            margin-bottom: 15px;
            text-shadow: 0 0 10px rgba(16, 124, 16, 0.5);
            font-weight: 700;
            letter-spacing: 0.5px;
        }}

        .description {{
            font-size: 1.1rem;
            margin-bottom: 30px;
            background: rgba(42, 42, 42, 0.7);
            padding: 20px;
            border-radius: 12px;
            border-left: 4px solid var(--primary);
            white-space: pre-wrap;
            line-height: 1.7;
        }}

        iframe {{
            width: 100%;
            height: 350px;
            border: none;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5);
        }}

        .section {{
            margin-bottom: 25px;
        }}

        .section-title {{
            font-size: 1.4rem;
            color: var(--accent);
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
        }}

        .section-title i {{
            color: var(--primary);
            font-size: 1.3rem;
        }}

        .code-box {{
            background: rgba(42, 42, 42, 0.7);
            padding: 18px;
            border-radius: 12px;
            position: relative;
            margin: 15px 0;
            border: 1px solid var(--border);
            transition: var(--transition);
        }}

        .code-box:hover {{
            background: rgba(50, 50, 50, 0.8);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
        }}

        .code-content {{
            padding-right: 15px;
            overflow: auto;
            font-size: 1.1rem;
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
            margin-top: 40px;
            padding: 25px;
            background: rgba(16, 124, 16, 0.2);
            border-radius: 12px;
            border-top: 2px solid var(--primary);
            border-bottom: 2px solid var(--primary);
        }}

        .fixed-images {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 40px;
            padding: 0 10px;
        }}

        .fixed-image-left,
        .fixed-image-right {{
            background-color: transparent;
            margin: 0;
            padding: 0;
        }}

        .fixed-images a {{
            transition: var(--transition);
        }}

        .fixed-images img {{
            width: 80px;
            height: auto;
            opacity: 0.85;
            transition: var(--transition);
            border-radius: 8px;
        }}

        .fixed-images img:hover {{
            opacity: 1;
            transform: scale(1.08);
        }}

        .company-logo {{
            display: block;
            margin: 40px auto 0;
            max-width: 300px;
            height: auto;
            opacity: 0.9;
            border-radius: 12px;
            padding: 10px;
            background: rgba(255, 255, 255, 0.05);
        }}

        #image-left, #image-right {{
            width: 120px;
            z-index: 999;
            border-radius: 10px;
            opacity: 0.9;
        }}

        #image-left {{
            float: left;
            margin-right: 20px;
            shape-outside: circle(50%);
        }}

        #image-right {{
            float: right;
            margin-left: 20px;
            shape-outside: circle(50%);
        }}

        .clearfix::after {{
            content: "";
            display: table;
            clear: both;
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            body {{
                padding: 15px;
            }}

            .container {{
                padding: 20px;
            }}

            h1 {{
                font-size: 2rem;
            }}

            .description {{
                font-size: 1rem;
                padding: 15px;
            }}

            iframe {{
                height: 250px;
            }}

            .section-title {{
                font-size: 1.2rem;
            }}

            .code-content {{
                font-size: 1rem;
            }}

            .header img {{
                max-width: 160px;
            }}

            .fixed-images img {{
                width: 65px;
            }}

            .company-logo {{
                max-width: 220px;
            }}

            #image-left, #image-right {{
                width: 90px;
                float: none;
                margin: 15px auto;
                display: block;
            }}
        }}

        @media (max-width: 480px) {{
            .container {{
                padding: 15px;
            }}

            h1 {{
                font-size: 1.8rem;
            }}

            iframe {{
                height: 200px;
            }}

            .fixed-images {{
                flex-direction: column;
                gap: 15px;
            }}

            .fixed-images img {{
                width: 70px;
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

        <div class="clearfix">
            <img id="image-left" src="{image_left_src}" />
            <img id="image-right" src="{image_right_src}" />
            
            <div class="section">
                <div class="section-title"><i class="fas fa-link"></i> Open <strong>Moonlight</strong> and Add:</div>
                <div class="code-box">
                    <div class="code-content">{ip_address}</div>
                </div>

                <div class="section-title"><i class="fas fa-mobile-alt"></i> Open <strong>iOS Moonlight</strong> and Add:</div>
                <div class="code-box">
                    <div class="code-content">{ios_address}</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-lock"></i> Enter 4-digit PIN here:</div>
                <div class="code-box">
                    <div class="code-content">
                        <a href="{pin_url}" target="_blank">{pin_url}</a>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-user-circle"></i> Use credentials:</div>
                <div class="code-box">
                    <div class="code-content">{credentials_sunshine}</div>
                </div>

                <div class="section-title"><i class="fas fa-desktop"></i> Windows Password:</div>
                <div class="code-box">
                    <div class="code-content">{windows_password}</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-download"></i> You need to download <strong>Moonlight</strong> to connect:</div>
                <div class="code-box">
                    <div class="code-content">
                        <a href="https://github.com/moonlight-stream/moonlight-qt/releases" target="_blank">
                            https://github.com/moonlight-stream/moonlight-qt/releases
                        </a>
                    </div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-cloud-upload-alt"></i> Upload files directly:</div>
                <div class="code-box">
                    <div class="code-content">
                        <a href="{drop_url}" target="_blank">{drop_url}</a>
                    </div>
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

        <div class="actions">
            <a id="new_vm_url" class="btn btn-primary" href="{new_vm_url}" target="_blank">
                <i class="fas fa-plus"></i> Create New VM
            </a>
            <a id="dash_url" class="btn btn-secondary" href="{dash_url}" target="_blank">
                <i class="fas fa-arrow-left"></i> Return to Dashboard
            </a>
        </div>

        <img class="company-logo" src="{company_src}"/>
    </div>
</body>

</html>
"""