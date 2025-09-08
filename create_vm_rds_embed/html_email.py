def HTMLEmail(ip_address:str, link1: str, link2: str, link3: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>Your VM is Ready</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            background-color: #121212;
            color: #f0f0f0;
            text-align: center;
            padding: 40px;
        }}
        a {{
            color: #00bfff;
            text-decoration: none;
            font-weight: bold;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .container {{
            max-width: 600px;
            margin: auto;
            background-color: #1e1e1e;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.5);
        }}
        .links {{
            margin-top: 20px;
        }}
        .links a {{
            display: block;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Your VM is Ready</h1>
        <p>Here are the links bamm:</p>
        <div class="links">
            <a href="{ip_address}" target="_blank">{ip_address}</a>
            <a href="{link1}" target="_blank">{link1}</a>
            <a href="{link2}" target="_blank">{link2}</a>
            <a href="{link3}" target="_blank">{link3}</a>
        </div>
    </div>
</body>
</html>"""