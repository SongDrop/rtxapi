def HTMLEmail(vhd_name: str, vhd_size_gib: float, sas_download_url: str, github_app_url: str):
    """
    vhd_name: e.g. "azure-os-disk_fixed.vhd"
    vhd_size_gib: file size in GiB (binary)
    sas_download_url: direct link to download VHD
    github_app_url: link to the app that flashes the VHD onto a USB
    """
    # Calculate decimal GB
    vhd_size_gb = vhd_size_gib * 1024**3 / 1_000_000_000  # binary GiB → decimal GB

    explanation = f"""
    📦 Your USB stick may be smaller than expected!
    - Manufacturer: shows decimal GB
    - OS: shows binary GiB
    - VHD file: {vhd_size_gib:.2f} GiB (~{vhd_size_gb:.2f} GB decimal)

    ⚖️ This means if your USB is advertised as {vhd_size_gib} GB, it will likely only show ~{vhd_size_gib * 1_000_000_000 / 1_073_741_824:.2f} GiB usable.
    The .vhd is slightly larger due to the binary/decimal mismatch — plan accordingly.
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>VHD Export Complete</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
body {{
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #0a527c, #1a7c9e, #38b6ff);
    color: #fff;
    margin: 0; padding: 0;
    display: flex; justify-content: center; align-items: center;
    min-height: 100vh;
}}
.container {{
    background: rgba(0,0,0,0.6);
    padding: 30px;
    border-radius: 12px;
    max-width: 700px;
    width: 100%;
}}
h1 {{ color: #00ffcc; text-align: center; }}
p {{ margin-bottom: 15px; line-height: 1.5; }}
a.btn {{
    display: inline-block; margin: 10px 5px; padding: 12px 20px;
    background: #1a73e8; color: white; text-decoration: none;
    border-radius: 6px; transition: 0.2s;
}}
a.btn:hover {{ background: #1664c1; }}
.code-box {{
    background: rgba(255,255,255,0.1); padding: 12px; border-radius: 6px;
    font-family: monospace; word-break: break-word;
}}
</style>
</head>
<body>
<div class="container">
    <h1>✅ Virtual Machine Export Complete</h1>
    <p>Your virtual OS disk <strong>{vhd_name}</strong> has been successfully exported!</p>

    <div class="section">
        <div class="section-title"><i class="fas fa-download"></i> Download VHD:</div>
        <div class="code-box">
            <a href="{sas_download_url}" target="_blank">{sas_download_url}</a>
        </div>
        <p>File size: {vhd_size_gib:.2f} GiB (~{vhd_size_gb:.2f} GB)</p>
        <p>{explanation}</p>
    </div>

    <div class="section">
        <div class="section-title"><i class="fas fa-rocket"></i> Flash to USB:</div>
        <a class="btn" href="{github_app_url}" target="_blank">
            Download USB Installer App
        </a>
    </div>
</div>
</body>
</html>
"""
