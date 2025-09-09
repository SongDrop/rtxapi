def HTMLEmail(snapshot_name: str, created_at: str, snapshot_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Snapshot Created</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f4f8;
            display: flex;
            justify-content: center;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 25px;
        }}
        .header h1 {{
            color: #4caf50;
        }}
        .snapshot-details {{
            background: #e8f5e9;
            border-left: 5px solid #4caf50;
            padding: 20px;
            border-radius: 10px;
        }}
        .detail-row {{
            margin-bottom: 10px;
        }}
        .detail-label {{
            font-weight: bold;
            color: #2e7d32;
        }}
        .link a {{
            color: #1565c0;
            text-decoration: none;
        }}
        .link a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            margin-top: 30px;
            font-size: 0.9rem;
            text-align: center;
            color: #555;
        }}
    </style>
</head>

<body>
    <div class="container">
        <div class="header">
            <div class="success-icon" style="font-size:3rem;color:#4caf50;">
                <i class="fas fa-check-circle"></i>
            </div>
            <h1>Snapshot Created Successfully!</h1>
            <p>Your virtual machine snapshot is now available.</p>
        </div>

        <div class="snapshot-details">
            <div class="detail-row">
                <span class="detail-label">Snapshot Name:</span> {snapshot_name}
            </div>
            <div class="detail-row">
                <span class="detail-label">Created At:</span> {created_at}
            </div>
            <div class="detail-row link">
                <span class="detail-label">Snapshot URL:</span> <a href="{snapshot_url}" target="_blank">{snapshot_url}</a>
            </div>
        </div>

        <div class="footer">
            <p>© 2025 Cloud Infrastructure Manager | For support, contact your administrator.</p>
        </div>
    </div>
</body>

</html>"""
