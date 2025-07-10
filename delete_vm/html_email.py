def HTMLEmail(ip_address:str,
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
    <meta name="author" content="RTXDevStation">
    <meta property="article:published_time" content="2025-04-19T10:00:00Z">
    <meta name="description" content="Your virtual machine is ready to use">
    <meta itemprop="name" content="{title}">
    <meta itemprop="description" content="Your virtual machine is ready to use">
    <meta itemprop="image" content="">
    <meta name="keywords" content="{title}">
    <meta property="og:title" content="{title}">
    <meta property="og:url" content="https://rtxdevstation.xyz">
    <meta property="og:type" content="website">
    <meta property="og:description" content="Your virtual machine is ready to use">
    <meta property="og:image" content="">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="Your virtual machine is ready to use">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:image" content="">
    <style>body {{ font-family: Arial, sans-serif; background-color: #121212; color: #f0f0f0; text-align: center; padding: 40px; background-position: center; background-repeat: no-repeat; background-size: cover; background-attachment: fixed; }}
a {{ color: #00bfff; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.container {{ max-width: 700px; margin: auto; background-color: #1e1e1e; padding: 30px; border-radius: 12px; box-shadow: 0 0 20px rgba(0, 0, 0, 0.5); }}
iframe {{ width: 100%; height: 400px; border: none; border-radius: 8px; margin-bottom: 20px; }}
.code, .download {{ background-color: #2a2a2a; padding: 10px; border-radius: 6px; font-family: monospace; margin: 10px 0; position: relative; }}
.download {{ margin-top: 40px; }}
.fixed-image-left, .fixed-image-right {{ position: fixed; bottom: 10px; width: 100px; z-index: 1000; pointer-events: none; }}
.fixed-image-left {{ left: 10px; }}
.fixed-image-right {{ right: 10px; }}
#image-left {{ position: fixed; bottom: 50px; left: 0; width: 100px; z-index: 999; }}
#image-right {{ position: fixed; bottom: 50px; right: 0; width: 100px; z-index: 999; }}
#d_main {{ white-space: pre-wrap; }}
#logo {{ width: 100%; }}
#company {{ height: 300px; }}
.copy-btn {{ display: inline-block; font-size: 16px; width: 20px; height: 20px; line-height: 20px; margin-left: 8px; cursor: pointer; vertical-align: middle; user-select: none; }}
@media (max-width: 600px) {{ body {{ padding: 20px; }} #image-left, #image-right {{ width: 80px; }} }}
.wrapper1 {{ display: block; text-align: center; background-color: #2a2a2a; margin: 0; padding: 0; height: auto; border-radius: 6px; }}
.wrapper {{ display: inline-flex; align-items: center; gap: 0px; height: 100%; margin: 0; padding: 0; margin-left: 16px; }}</style>
</head>

<body>
    <div class="container">
        <img id="logo" />
        <h1 id="t_main">{main_heading}</h1>
        <p id="d_main">{main_description}</p>

        <iframe id='y_main' src="{youtube_embed_src}" allowfullscreen></iframe>

        <p>Open <strong>Moonlight</strong> and Add:</p>
        <div class="code" id="ipAddress">0.0.0.0</div>
        <p>Open <strong>iOS Moonlight</strong> and Add:</p>
        <div class="code" id="iOSAddress">0.0.0.0</div>

        <p>Enter 4-digit PIN here:</p>
        <a href="" target="_blank" id="pinLink">0.0.0.0</a>

        <p>Use credentials:</p>
        <div class="code" id="credentials">{credentials_sunshine}</div>

        <p>Windows Password:</p>
        <div class="code" id="winPass">{windows_password}</div>

        <p>You need to download Moonlight to connect:</p>
        <a href="https://github.com/moonlight-stream/moonlight-qt/releases" target="_blank">
            https://github.com/moonlight-stream/moonlight-qt/releases
        </a>

        <div class="download">
            <div id="formdesc">{form_description}</div>
            <a href="{form_link}" target="_blank" id="vhdLink">{form_link}</a>
        </div>
        <br />
        <iframe id='discord' src="{discord_widget_src}" width="100%" height="400" allowtransparency="true" frameborder="0"
            sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin allow-scripts"></iframe>
    </div>

    <a href="https://portal.azure.com" class="fixed-image-left" target="_blank">
        <img src="https://i.ibb.co/459vKcy/azure.png" alt="azure" width="100">
    </a>
    <a href="https://rtxdevstation.xyz" class="fixed-image-right" target="_blank">
        <img src="https://i.ibb.co/mChg6mrj/nvidiartx.png" alt="nvidiartx" width="100">
    </a>

    <img id="image-left" src="{image_left_src}" />
    <img id="image-right" src="{image_right_src}" />
    <br />
    <img id='company' src="{company_src}" />

    <script>
        function getQueryParam(name) {{
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get(name);
        }}

        function copyToClipboard(id) {{
            const el = document.getElementById(id);
            if (!el) return;

            const range = document.createRange();
            range.selectNodeContents(el);
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(range);
            try {{
                document.execCommand("copy");
                sel.removeAllRanges();
            }} catch (err) {{
                alert("Copy failed.");
            }}
        }}

        function addCopyButton(targetId) {{
            const el = document.getElementById(targetId);
            if (!el) return;

            if (document.getElementById(`${{targetId}}-copy-btn`)) return;

            const wrapper1 = document.createElement('div');
            wrapper1.classList.add('wrapper1');
            wrapper1.style.height = `${{el.offsetHeight}}px`;

            const wrapper = document.createElement('div');
            wrapper.classList.add('wrapper');

            const clone = el.cloneNode(true);
            wrapper.appendChild(clone);
            wrapper1.appendChild(wrapper);
            clone.removeAttribute('style');

            el.replaceWith(wrapper1);
            clone.id = targetId;

            const btn = document.createElement('button');
            btn.className = 'copy-btn';
            btn.id = `${{targetId}}-copy-btn`;
            btn.textContent = '📋';
            btn.style.cursor = 'pointer';
            btn.style.border = 'none';
            btn.style.background = 'none';
            btn.style.color = '#00bfff';
            btn.style.fontSize = '1em';
            btn.style.userSelect = 'none';
            btn.style.padding = '0';
            btn.style.margin = '0';

            btn.onclick = async (e) => {{
                e.preventDefault();
                e.stopPropagation();
                try {{
                    const text = clone.textContent.trim();
                    await navigator.clipboard.writeText(text);
                    console.log('Copied:', text);
                }} catch (err) {{
                    console.error('Copy failed:', err);
                }}
            }};

            wrapper.appendChild(btn);
        }}

       

        window.onload = () => {{
            document.body.style.backgroundImage = "url('{background_image_url}')";
            document.title = '{title}';
            document.getElementById('t_main').textContent = '{main_heading}';
            document.getElementById('d_main').textContent = '{main_description}';
            document.getElementById('y_main').src = '{youtube_embed_src}';
            document.getElementById('image-left').src = '{image_left_src}';
            document.getElementById('image-right').src = '{image_right_src}';
            document.getElementById('logo').src = '{logo_src}';
            document.getElementById('company').src = '{company_src}';
            document.getElementById('discord').src = '{discord_widget_src}';
            document.getElementById('winPass').textContent = '{windows_password}';
            document.getElementById('credentials').innerHTML = `{credentials_sunshine}`;
            document.getElementById('formdesc').textContent = '{form_description}';
            updateContent();
        }};

         function updateContent() {{
            const ipAddress = getQueryParam('url');
            const formUrl = getQueryParam('form');

            if (ipAddress && formUrl) {{
                document.getElementById('ipAddress').textContent = {ip_address};
                document.getElementById('iOSAddress').textContent = `[::ffff:{ip_address}]`;
                document.getElementById('pinLink').href = `https://{ip_address}:47990/pin`;
                document.getElementById('pinLink').textContent = `https://{ip_address}:47990/pin`;
                document.getElementById('vhdLink').href = formUrl;
                document.getElementById('vhdLink').textContent = formUrl;
            }}

            addCopyButton('ipAddress');
            addCopyButton('iOSAddress');
            addCopyButton('credentials');
            addCopyButton('winPass');

            const pinLink = document.getElementById('pinLink');
            if (pinLink && !document.getElementById('pinCopy')) {{
                const btn = document.createElement('span');
                btn.className = 'copy-btn';
                btn.id = 'pinCopy';
                btn.innerHTML = '📋';
                btn.onclick = () => {{
                    const temp = document.createElement('input');
                    document.body.appendChild(temp);
                    temp.value = pinLink.href;
                    temp.select();
                    document.execCommand('copy');
                    document.body.removeChild(temp);
                }};
                pinLink.parentNode.insertBefore(btn, pinLink.nextSibling);
            }}
        }}
    </script>
</body>

</html>"""