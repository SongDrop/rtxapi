def HTMLEmail(snapshot_vm: str, vhd_download_url: str, vhdusb_app_url: str, design_files_url: str, github_repo_url: str):
    """
    snapshot_vm: The name of the snapshot VM
    vhd_download_url: Direct download URL for the VHD file
    vhdusb_app_url: URL to download the VHDUSBDownloader app
    design_files_url: URL for design files (3D models, box art)
    github_repo_url: URL for the GitHub repository
    """
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VHD Conversion Completed</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f4f4;
            margin: 0;
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 700px;
            margin: auto;
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            color: #2e7d32;
            text-align: center;
        }}

        p {{
            font-size: 1rem;
            line-height: 1.5;
            margin-bottom: 15px;
        }}

        .section {{
            margin-bottom: 30px;
        }}

        .vm-details {{
            background: #f1f8e9;
            border-left: 5px solid #4caf50;
            padding: 20px;
            border-radius: 5px;
        }}

        .detail-row {{
            margin-bottom: 10px;
        }}

        .detail-label {{
            font-weight: bold;
        }}

        .btn {{
            display: inline-block;
            padding: 12px 25px;
            margin: 10px 5px 0 0;
            border-radius: 5px;
            text-decoration: none;
            font-weight: bold;
            color: white;
        }}

        .btn-primary {{
            background-color: #3498db;
        }}

        .btn-primary:hover {{
            background-color: #2980b9;
        }}

        .btn-secondary {{
            background-color: #2ecc71;
        }}

        .btn-secondary:hover {{
            background-color: #27ae60;
        }}

        .footer {{
            font-size: 0.85rem;
            text-align: center;
            color: #555;
            margin-top: 40px;
        }}

        .link {{
            word-break: break-all;
            color: #1a73e8;
            text-decoration: underline;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.95rem;
        }}

        th,
        td {{
            border: 1px solid #ccc;
            padding: 8px;
        }}

        th {{
            background: #f1f8e9;
            text-align: left;
        }}

        td.center {{
            text-align: center;
        }}

        td.right {{
            text-align: right;
        }}

        td.success {{
            background: #e0f7e9;
        }}

        td.error {{
            background: #fde0e0;
        }}

        .flex-images {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            justify-content: center;
        }}

        .flex-images div {{
            flex: 1 1 45%;
            text-align: center;
        }}

        .flex-images img {{
            width: 100%;
            max-width: 200px;
            border-radius: 8px;
        }}

        .timeline-horizontal {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin: 30px 0;
            position: relative;
        }}

        .timeline-horizontal::before {{
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            width: 100%;
            height: 3px;
            background: #ccc;
            z-index: 0;
        }}

        .timeline-step-h {{
            position: relative;
            z-index: 1;
            background: #4caf50;
            color: white;
            font-weight: bold;
            text-align: center;
            padding: 8px 14px;
            border-radius: 20px;
            font-size: 0.95rem;
        }}

        .timeline-step-h.done::after {{
            content: '✔️';
            margin-left: 6px;
        }}

        .timeline-step-h.download {{
            background: #2196f3;
        }}

        .timeline-step-h.download::after {{
            content: '⬇️';
            margin-left: 6px;
        }}

        .conversion-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
            font-size: 0.75rem;
        }}

        .conversion-table th,
        .conversion-table td {{
            border: 1px solid #ccc;
            padding: 10px;
            vertical-align: top;
            background: white;

        }}

        .conversion-table th {{
            text-align: left;
            width: 60%;
            font-weight: normal;
        }}

        .conversion-table td {{
            text-align: right;
            font-weight: 500;
        }}
    </style>
</head>

<body>
    <div class="container">
        <h1>✅ Hyper-V Disk Conversion Successful</h1>

        <div class="section">
            <p>Your virtual machine snapshot has been successfully converted and resized using Hyper-V technology. The
                original snapshot was <strong>256GB</strong> and has been optimized to <strong>220GB</strong> for
                efficient storage and faster access.</p>

            <p>You can now download this VHD using the <strong>VHDUSBDownloader</strong> app — a lightweight tool that
                safely copies large VHD files directly to your USB drive. Simply copy the link below into the app to
                start the transfer:</p>

            <p>📦 <strong>Download Note:</strong> The file is large (<strong>220GB</strong>), so the download may take
                ~8-10 hours on a 10Mbps connection. We recommend using a stable, wired connection and keeping your
                computer powered on.</p>
        </div>
        <div class="timeline-horizontal">
            <div class="timeline-step-h done">Snapshot</div>
            <div class="timeline-step-h done">Hyper-V</div>
            <div class="timeline-step-h done">.vhd</div>
            <div class="timeline-step-h download">Download</div>
        </div>

        <div class="section vm-details">
            <div class="detail-row"><span class="detail-label">Snapshot Name:</span> <span>{snapshot_vm}</span></div>
            <div class="detail-row"><span class="detail-label">Conversion Time:</span> <span>
                    <table class="conversion-table">
                        <tr>
                            <th>✅ Create Snapshot</th>
                            <td>~10 minutes</td>
                        </tr>
                        <tr>
                            <th>✅ Create Hyper-V (Standard_D4s_v3)</th>
                            <td>~15 minutes</td>
                        </tr>
                        <tr>
                            <th>✅ Download 256 GB snapshot (Hyper-V conversion)</th>
                            <td>~1 hour (network-dependent)</td>
                        </tr>
                        <tr>
                            <th>✅ Hyper-V Conversion (dynamic → compact → fixed)</th>
                            <td>~2 hours</td>
                        </tr>
                        <tr>
                            <th>✅ Upload to storage (azcopy)</th>
                            <td>~1 hour</td>
                        </tr>
                        <tr>
                            <th>✅ Cleanup Hyper-V and Snapshot</th>
                            <td>~10 minutes</td>
                        </tr>
                        <tr>
                            <th><strong>⬇️ Download VHD to USB (VHDUSBDownloader)</strong></th>
                            <td><strong>~10 hours (10Mbps) <br><small>(up to 120Mbps faster)</small></strong>
                            </td>
                        </tr>

                    </table>
                </span>
            </div>
            <div class="detail-row"><span class="detail-label">Status:</span> <span>Completed</span></div>
            <div class="detail-row"><span class="detail-label">Download URL for VHD:</span><br>
                <span class="link">{vhd_download_url}</span>
            </div>
        </div>

        <div class="section">
            <h2>Recommended USB Drives for Your VHD</h2>
            <p>To store your optimized <strong>220GB VHD</strong>, here are compatible USB drives:</p>
            <div class="flex-images">
                <div>
                    <img src="https://i.postimg.cc/15LtWMHN/256gb-fit-plus-usb.png" alt="Samsung 256GB USB">
                    <p><a href="https://www.samsung.com/uk/memory-storage/usb-flash-drive/usb-flash-drive-fit-plus-256gb-black-muf-256ab-apc/"
                            target="_blank">256GB USB</a></p>
                </div>
                <div>
                    <img src="https://i.postimg.cc/pTGVKBrr/512gb-fit-plus-usb.png" alt="Samsung 512GB USB">
                    <p><a href="https://www.samsung.com/uk/memory-storage/usb-flash-drive/usb-flash-drive-fit-plus-512gb-black-muf-512ab-apc/"
                            target="_blank">512GB USB</a></p>
                </div>
            </div>
        </div>

        <div class="section">
            <p style="margin-top:15px;">Note: USB drives and VHDs use different definitions of "GB":</p>
            <div>- <strong>USB drives:</strong> Decimal GB (1 GB = 1,000,000,000 bytes)</div>
            <div>- <strong>VHD disks:</strong> Binary GB (1 GB = 1,073,741,824 bytes)</div>

            <p>For example, an exported OS disk of <strong>256 GB</strong> would not fit on a USB labeled as 256 GB.
                That's why the disk was resized during conversion, reducing it from 256 GB to 220 GB to ensure it fits
                safely on typical USB drives.</p>

            <table>
                <tr>
                    <th></th>
                    <th>Before Conversion</th>
                    <th class="center">USB Fit?</th>
                    <th>After Conversion</th>
                    <th class="center">USB Fit?</th>
                </tr>
                <tr>
                    <th>VHD Size (Bytes)</th>
                    <td class="right error">256 × 1,073,741,824 = 274,877,906,944</td>
                    <td class="center error">❌ Too large</td>
                    <td class="right success">220 × 1,073,741,824 = 236,222,120,320</td>
                    <td class="center success">✅ Fits USB</td>
                </tr>
                <tr>
                    <th>Equivalent USB GB</th>
                    <td class="right error">≈ 274.88 GB</td>
                    <td class="center error">❌ Too large</td>
                    <td class="right success">≈ 236.22 GB</td>
                    <td class="center success">✅ Fits USB</td>
                </tr>
            </table>
        </div>

        <div class="section">
            <p>You can download the <strong>VHDUSBDownloader</strong> from the following links:</p>
            <a href="{vhdusb_app_url}" class="btn btn-primary" target="_blank">VHDUSBDownloader (Windows)</a>
            <a href="{vhdusb_app_url}" class="btn btn-secondary" target="_blank">VHDUSBDownloader (MacOSX)</a>
        </div>

        <div class="section">
            <p>Simply copy the VHD download link above and paste it into the VHDUSB Downloader app to start downloading
                your optimized disk.</p>
        </div>

        <div class="section">
            <h2>Create Box Art & 3D Case</h2>
            <p>Take your virtual machine projects to the next level by designing custom
                <strong>box art</strong> and a <strong>3D-printed case</strong> for your team’s
                portable development environment. Perfect for showcasing your work, building
                team identity, or preparing demo-ready kits.
            </p>

            <div style="display: flex; gap: 20px; flex-wrap: wrap; justify-content: center; margin-top: 20px;">
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/4xGB0m5T/INSERT-A4.png" alt="Box Art Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>Insert</strong><br>
                        Create insert artwork for your 3d case.</p>
                </div>
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/wjFcbFMP/MANUAL-A4.png" alt="Box Art Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>Manual</strong><br>
                        Create manual for your 3d case</p>
                </div>
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/6p6CRRc5/BOXART-A4-BACK.png" alt="3D Case Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>Box Art Hard Paper Back</strong><br>
                        Create box art from hard paper for your 3d case</p>
                </div>
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/jdbHxBJP/BOXART-A4-FRONT.png" alt="3D Case Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>Box Art Hard Paper Front</strong><br>
                        Create box art from hard paper for your 3d case</p>
                </div>
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/44FDjb7Y/hyperv-usb.png" alt="3D Case Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>3d printed USB HEAD</strong><br>
                        Print 3d head for SAMSUNG Fit-Plus usb</p>
                </div>
                <div style="flex: 1 1 45%; text-align: center;">
                    <img src="https://i.postimg.cc/kXJ2hCS7/3-DCASE-CLOSED.png" alt="3D Case Example"
                        style="width:100%; max-width:250px; border-radius: 8px; box-shadow:0 4px 10px rgba(0,0,0,0.1);">
                    <p><strong>3d printed USB CASE</strong><br>
                        Print 3d case for SAMSUNG Fit-Plus usb</p>
                </div>
            </div>

            <p style="margin-top:15px;">Guide to design, print, and share
                your own <strong>development box art & cases</strong> for collaboration or team distribution.</p>
            <a href="{design_files_url}" class="btn btn-secondary" target="_blank">Download 3D Models</a>
            <a href="{design_files_url}" class="btn btn-primary" target="_blank">Design Box art</a>

        </div>
        <div class="section">
            <h2>🌍 Share Your Build with the Community</h2>
            <p>Contribute back by sharing your custom development box. Add a screenshot of your
                desktop and the storage link for your <strong>bootable-fixed.vhd</strong>. This allows
                others to quickly clone and test your virtual images.</p>

            <p>Just commit the following JSON file to our <strong>GitHub</strong> repository:</p>

            <pre
                style="background:#f9f9f9; padding:15px; border-radius:6px; font-size:0.9rem; overflow-x:auto; border:1px solid #ddd;">
{{
  "url": "sas_token_url_for_storage",
  "vm_name": "ue3dhxm-117293-fixed-bootable.vhd",
  "size_in_gb": "220",
  "image_url": "screenshot_of_desktop_url"
}}
  </pre>

            <p style="margin-top:15px;">🔗 Once submitted, your build will be listed in the community gallery so others
                can
                explore and use it in their own virtual machines.</p>

            <a href="{github_repo_url}" class="btn btn-primary" target="_blank">📤 Contribute on GitHub</a>
        </div>

        <div class="footer">
            <p>© 2025 Cloud Infrastructure Manager | All operations are logged for security purposes</p>
        </div>
    </div>
</body>

</html>"""