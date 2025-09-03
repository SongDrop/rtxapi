def HTMLEmail(ip_address: str, created_at: str, link1: str, rdpgen: str,  new_vm_url: str, dash_url: str,  username: str, password: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Virtual Machine is Ready</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}

        body {{
            background: linear-gradient(135deg, #0a527c, #1a7c9e, #38b6ff);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            color: #333;
        }}

        .container {{
            width: 100%;
            max-width: 800px;
            background: rgba(255, 255, 255, 0.97);
            border-radius: 20px;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.2);
            overflow: hidden;
        }}

        .header {{
            background: #2c3e50;
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.9;
        }}

        .content {{
            padding: 40px;
        }}

        .creation-message {{
            text-align: center;
            margin-bottom: 40px;
        }}

        .creation-message h2 {{
            font-size: 2.8rem;
            color: #2e7d32;
            margin-bottom: 20px;
            letter-spacing: 1px;
        }}

        .vm-details {{
            background: #e3f2fd;
            border-radius: 15px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.05);
            border-left: 5px solid #2196f3;
        }}

        .detail-row {{
            display: flex;
            justify-content: space-between;
            padding: 15px 0;
            border-bottom: 1px solid #bbdefb;
        }}

        .detail-row:last-child {{
            border-bottom: none;
        }}

        .detail-label {{
            font-weight: 600;
            color: #1565c0;
            font-size: 1.2rem;
        }}

        .detail-value {{
            font-weight: 500;
            color: black;
            font-size: 1.2rem;
        }}

        .links-container {{
            margin-top: 30px;
        }}

        .link-item {{
            display: flex;
            align-items: center;
            padding: 15px;
            margin: 15px 0;
            background: #f5f5f5;
            border-radius: 10px;
            transition: all 0.3s ease;
        }}

        .link-item:hover {{
            background: #e8f5e9;
            transform: translateX(5px);
        }}

        .link-icon {{
            margin-right: 15px;
            font-size: 1.5rem;
            color: #2196f3;
        }}

        .link-text {{
            flex-grow: 1;
        }}

        .link-text a {{
            color: #1565c0;
            text-decoration: none;
            font-weight: 600;
        }}

        .link-text a:hover {{
            text-decoration: underline;
        }}

        .link-description {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 5px;
        }}

        .actions {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 40px;
            flex-wrap: wrap;
        }}

        .btn {{
            padding: 15px 30px;
            border-radius: 50px;
            font-size: 1.1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
        }}

        .btn-primary {{
            background: #3498db;
            color: white;
        }}

        .btn-primary:hover {{
            background: #2980b9;
            transform: translateY(-3px);
        }}

        .btn-secondary {{
            background: #e9ecef;
            color: #2c3e50;
        }}

        .btn-secondary:hover {{
            background: #dee2e6;
            transform: translateY(-3px);
        }}

        .footer {{
            background: #e3f2fd;
            padding: 20px;
            text-align: center;
            font-size: 0.9rem;
            color: black;
        }}

        .success-icon {{
            font-size: 4rem;
            color: #4caf50;
            margin-bottom: 20px;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 2rem;
            }}

            .creation-message h2 {{
                font-size: 2rem;
            }}

            .detail-row {{
                flex-direction: column;
                gap: 5px;
            }}

            .actions {{
                flex-direction: column;
                align-items: center;
            }}
            
            .btn {{
                width: 100%;
                max-width: 280px;
                justify-content: center;
            }}
        }}
    </style>
</head>

<body>
    <div class="container">
        <div class="header">
            <h1><i class="fas fa-server"></i> Virtual Machine Management</h1>
            <p>Your cloud resources are ready</p>
        </div>

        <div class="content">
            <div class="creation-message">
                <div class="success-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <h2>Virtual Machine Successfully Created</h2>
                <p>Your new virtual machine is now running and ready for use.</p>
            </div>

            <div class="vm-details">
                <div class="detail-row">
                    <span class="detail-label">IP Address:</span>
                    <span class="detail-value" id="ip-address"> {ip_address}</span>
                </div>
                 <div class="detail-row">
                    <span class="detail-label">Username:</span>
                    <span class="detail-value">{username}</span>
                </div>

                <div class="detail-row">
                    <span class="detail-label">Password:</span>
                    <span class="detail-value">{password}</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">Status:</span>
                    <span class="detail-value"> Running</span>
                </div>

                <div class="detail-row">
                    <span class="detail-label">Creation Time:</span>
                    <span class="detail-value" id="creation-time"> {created_at}</span>
                </div>
            </div>

            <div class="links-container">
                <div class="link-item">
                    <div class="link-icon">
                        <i class="fas fa-globe"></i>
                    </div>
                    <div class="link-text">
                        <a href="{link1}" target="_blank">{link1}</a>
                        <div class="link-description">Direct access to your virtual machine</div>
                    </div>
                </div>
                <div class="link-item">
                    <div class="link-icon">
                        <i class="fas fa-globe"></i>
                    </div>
                    <div class="link-text">
                        <a href="{rdpgen}" target="_blank">{rdpgen}</a>
                        <div class="link-description">Connect with Remote Desktop Solution</div>
                    </div>
                </div>
                <div class="link-item">
                    <div class="link-icon">
                        <i class="fas fa-link"></i>
                    </div>
                    <div class="link-text">
                        <a href="{ip_address}" target="_blank">Primary Access URL</a>
                        <div class="link-description">Access your deployed application</div>
                    </div>
                </div>
            </div>

             <div class="actions">
                <a id="new_vm_url" class="btn btn-primary" href="{new_vm_url}" target="_blank">
                    <i class="fas fa-plus"></i> Create New VM
                </a>
                <a id="dash_url" class="btn btn-secondary" href="{dash_url}" target="_blank">
                    <i class="fas fa-arrow-left"></i> Return to Dashboard
                </a>
            </div>
        </div>

        <div class="footer">
            <p>© 2025 Cloud Infrastructure Manager | Need help? Contact our support team</p>
        </div>
    </div>
</body>

</html>"""