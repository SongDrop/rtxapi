import logging
import os
import json
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from urllib.parse import quote, unquote

def generate_folder_icon():
    """Generate a simple folder icon using SVG"""
    return """
    <svg width="20" height="16" viewBox="0 0 20 16" style="vertical-align: middle; margin-right: 8px;">
        <path d="M18,2H9L7,0H2C0.9,0,0,0.9,0,2v12c0,1.1,0.9,2,2,2h16c1.1,0,2-0.9,2-2V4C20,2.9,19.1,2,18,2z" 
              fill="#ffd04d" stroke="#e6a700" stroke-width="1"/>
    </svg>
    """

def generate_container_icon():
    """Generate a container/storage icon"""
    return """
    <svg width="20" height="20" viewBox="0 0 20 20" style="vertical-align: middle; margin-right: 8px;">
        <rect x="2" y="2" width="16" height="16" rx="2" fill="#0078d4" stroke="#106ebe" stroke-width="1"/>
        <rect x="6" y="6" width="8" height="2" fill="white"/>
        <rect x="6" y="10" width="6" height="2" fill="white"/>
        <rect x="6" y="14" width="4" height="2" fill="white"/>
    </svg>
    """

def generate_file_icon(file_extension):
    """Generate appropriate file icon based on file extension"""
    colors = {
        '.txt': '#4CAF50', '.pdf': '#f44336', '.doc': '#2196F3', '.docx': '#2196F3',
        '.xls': '#4CAF50', '.xlsx': '#4CAF50', '.zip': '#FF9800', '.rar': '#FF9800',
        '.jpg': '#9C27B0', '.png': '#9C27B0', '.mp4': '#795548', '.mp3': '#009688',
        'default': '#607D8B'
    }
    
    color = colors.get(file_extension.lower(), colors['default'])
    
    return f"""
    <svg width="16" height="20" viewBox="0 0 16 20" style="vertical-align: middle; margin-right: 8px;">
        <path d="M14,0H2C0.9,0,0,0.9,0,2v16c0,1.1,0.9,2,2,2h12c1.1,0,2-0.9,2-2V2C16,0.9,15.1,0,14,0z M14,18H2V2h12V18z" 
              fill="{color}"/>
        <rect x="4" y="4" width="8" height="2" fill="white"/>
        <rect x="4" y="8" width="8" height="2" fill="white"/>
        <rect x="4" y="12" width="6" height="2" fill="white"/>
    </svg>
    """

def format_file_size(size_bytes):
    """Convert bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def generate_breadcrumb(current_container, current_path):
    """Generate breadcrumb navigation"""
    breadcrumb = ['<div class="breadcrumb">']
    breadcrumb.append('<a href="?">Storage Account</a>')
    
    if current_container:
        breadcrumb.append(f'<span class="separator">/</span>')
        if current_path:
            breadcrumb.append(f'<a href="?container={quote(current_container)}">{current_container}</a>')
        else:
            breadcrumb.append(f'<span class="current">{current_container}</span>')
    
    if current_path:
        parts = current_path.strip('/').split('/')
        current_path_so_far = ""
        for i, part in enumerate(parts):
            current_path_so_far += f"/{part}" if current_path_so_far else part
            if i == len(parts) - 1:
                breadcrumb.append(f'<span class="separator">/</span><span class="current">{part}</span>')
            else:
                breadcrumb.append(f'<span class="separator">/</span><a href="?container={quote(current_container)}&path={quote(current_path_so_far)}">{part}</a>')
    
    breadcrumb.append('</div>')
    return ''.join(breadcrumb)

def list_containers(connection_string):
    """List all containers in the storage account"""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        containers = blob_service_client.list_containers()
        
        container_list = []
        for container in containers:
            container_list.append({
                'name': container.name,
                'last_modified': container.last_modified.strftime('%Y-%m-%d %H:%M:%S') if container.last_modified else 'Unknown'
            })
        
        return container_list, None
        
    except Exception as e:
        logging.error(f"Error listing containers: {e}")
        return None, str(e)

def list_container_items(connection_string, container_name, prefix=""):
    """List blobs and virtual folders in a container"""
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Ensure container exists
        if not container_client.exists():
            return None, None, f"Container '{container_name}' not found"
        
        blobs = container_client.list_blobs(name_starts_with=prefix)
        
        folders = []
        files = []
        seen_folders = set()
        
        for blob in blobs:
            # Remove the prefix from the blob name for display
            display_name = blob.name[len(prefix):] if prefix else blob.name
            
            if '/' in display_name:
                # This blob is in a subfolder
                folder_name = display_name.split('/')[0]
                folder_path = prefix + folder_name + '/' if prefix else folder_name + '/'
                
                if folder_path not in seen_folders:
                    seen_folders.add(folder_path)
                    folders.append({
                        'name': folder_name,
                        'path': folder_path.rstrip('/')
                    })
            else:
                # This is a file in the current directory
                files.append({
                    'name': display_name,
                    'full_path': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified.strftime('%Y-%m-%d %H:%M:%S') if blob.last_modified else 'Unknown'
                })
        
        return folders, files, None
        
    except Exception as e:
        logging.error(f"Error listing container items: {e}")
        return None, None, str(e)

def generate_storage_html(containers, folders, files, current_container, current_path, connection_string):
    """Generate HTML for storage browser"""
    
    # If no container specified, show storage account view
    if not current_container:
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Azure Storage Account</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                    color: #242424;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #0078d4;
                    border-bottom: 2px solid #0078d4;
                    padding-bottom: 10px;
                }
                .stats {
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                    font-size: 14px;
                    color: #6c757d;
                }
                .file-list {
                    list-style: none;
                    padding: 0;
                }
                .file-item {
                    display: flex;
                    align-items: center;
                    padding: 12px 15px;
                    border-bottom: 1px solid #e0e0e0;
                    transition: background-color 0.2s;
                    text-decoration: none;
                    color: inherit;
                }
                .file-item:hover {
                    background-color: #f8f9fa;
                }
                .file-item.container-item:hover {
                    background-color: #e3f2fd;
                }
                .file-icon {
                    margin-right: 12px;
                    flex-shrink: 0;
                }
                .file-info {
                    flex-grow: 1;
                }
                .file-name {
                    font-weight: 500;
                    margin-bottom: 2px;
                    color: #0078d4;
                }
                .file-details {
                    font-size: 12px;
                    color: #6c757d;
                }
                .empty-state {
                    text-align: center;
                    padding: 40px 20px;
                    color: #6c757d;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Azure Storage Account</h1>
                <div class="stats">
                    📊 Total Containers: {container_count}
                </div>
        """.format(container_count=len(containers))
        
        if containers:
            html_content += '<ul class="file-list">'
            for container in containers:
                html_content += f"""
                    <a href="?container={quote(container['name'])}" class="file-item container-item">
                        <div class="file-icon">{generate_container_icon()}</div>
                        <div class="file-info">
                            <div class="file-name">{container['name']}</div>
                            <div class="file-details">Container • Last modified: {container['last_modified']}</div>
                        </div>
                    </a>
                """
            html_content += '</ul>'
        else:
            html_content += """
                <div class="empty-state">
                    <p>No containers found in this storage account</p>
                </div>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
    
    else:
        # Show container view
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Azure Storage - {current_container}</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                    color: #242424;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 20px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #0078d4;
                    border-bottom: 2px solid #0078d4;
                    padding-bottom: 10px;
                }}
                .breadcrumb {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                    font-size: 14px;
                }}
                .breadcrumb a {{
                    color: #0078d4;
                    text-decoration: none;
                }}
                .breadcrumb a:hover {{
                    text-decoration: underline;
                }}
                .breadcrumb .separator {{
                    margin: 0 8px;
                    color: #6c757d;
                }}
                .breadcrumb .current {{
                    color: #495057;
                    font-weight: bold;
                }}
                .stats {{
                    background: #f8f9fa;
                    padding: 15px;
                    border-radius: 4px;
                    margin-bottom: 20px;
                    font-size: 14px;
                    color: #6c757d;
                }}
                .file-list {{
                    list-style: none;
                    padding: 0;
                }}
                .file-item {{
                    display: flex;
                    align-items: center;
                    padding: 12px 15px;
                    border-bottom: 1px solid #e0e0e0;
                    transition: background-color 0.2s;
                }}
                .file-item.folder {{
                    text-decoration: none;
                    color: inherit;
                }}
                .file-item:hover {{
                    background-color: #f8f9fa;
                }}
                .file-item.folder:hover {{
                    background-color: #e3f2fd;
                }}
                .file-icon {{
                    margin-right: 12px;
                    flex-shrink: 0;
                }}
                .file-info {{
                    flex-grow: 1;
                }}
                .file-name {{
                    font-weight: 500;
                    margin-bottom: 2px;
                    color: #0078d4;
                }}
                .file-details {{
                    font-size: 12px;
                    color: #6c757d;
                }}
                .file-size {{
                    font-family: 'Courier New', monospace;
                    color: #495057;
                    margin-right: 15px;
                }}
                .file-date {{
                    color: #6c757d;
                }}
                .download-btn {{
                    background: #28a745;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 4px;
                    cursor: pointer;
                    text-decoration: none;
                    font-size: 12px;
                    transition: background-color 0.2s;
                }}
                .download-btn:hover {{
                    background: #218838;
                }}
                .empty-state {{
                    text-align: center;
                    padding: 40px 20px;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Azure Storage Container: {current_container}</h1>
                {generate_breadcrumb(current_container, current_path)}
                <div class="stats">
                    📊 Statistics: {folder_count} folder(s), {file_count} file(s), Total size: {total_size}
                </div>
        """.format(
            folder_count=len(folders),
            file_count=len(files),
            total_size=format_file_size(sum(blob['size'] for blob in files))
        )
        
        # Add folders first
        if folders:
            html_content += '<ul class="file-list">'
            for folder in folders:
                encoded_path = quote(folder['path'])
                html_content += f"""
                    <a href="?container={quote(current_container)}&path={encoded_path}" class="file-item folder">
                        <div class="file-icon">{generate_folder_icon()}</div>
                        <div class="file-info">
                            <div class="file-name">{folder['name']}</div>
                            <div class="file-details">Folder</div>
                        </div>
                    </a>
                """
        
        # Add files
        if files:
            if not folders:  # Only add list if we haven't already started one
                html_content += '<ul class="file-list">'
            
            for blob in files:
                file_extension = os.path.splitext(blob['name'])[1].lower()
                file_size = format_file_size(blob['size'])
                
                # Generate download URL
                blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                blob_client = blob_service_client.get_blob_client(container=current_container, blob=blob['full_path'])
                download_url = blob_client.url
                
                html_content += f"""
                    <div class="file-item">
                        <div class="file-icon">{generate_file_icon(file_extension)}</div>
                        <div class="file-info">
                            <div class="file-name">{blob['name']}</div>
                            <div class="file-details">
                                <span class="file-size">{file_size}</span>
                                <span class="file-date">{blob['last_modified']}</span>
                            </div>
                        </div>
                        <a href="{download_url}" class="download-btn" download="{blob['name']}">Download</a>
                    </div>
                """
            
            html_content += '</ul>'
        
        # Empty state
        if not folders and not files:
            html_content += """
                <div class="empty-state">
                    <p>This folder is empty</p>
                </div>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
    
    return html_content

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing request to list Azure Storage containers and blobs.')

    try:
        # Parse inputs - prefer POST JSON body, fallback to query params
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}

        # Get container and path from both JSON and query params
        container_name = req_body.get('container') or req.params.get('container', '')
        path_name = req_body.get('path') or req.params.get('path', '')
        
        if path_name:
            path_name = unquote(path_name)

        # Get connection string from environment
        connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        if not connection_string:
            err = "AZURE_STORAGE_CONNECTION_STRING environment variable is not set."
            logging.error(err)
            # Return HTML error
            error_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Error</title>
                <style>
                    body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
                    .error {{ color: #d13438; background: #fdf2f2; padding: 15px; border-radius: 4px; }}
                </style>
            </head>
            <body>
                <div class="error">
                    <h2>Configuration Error</h2>
                    <p>{err}</p>
                </div>
            </body>
            </html>
            """
            return func.HttpResponse(
                error_html,
                status_code=500,
                mimetype="text/html"
            )

        # If no container specified, list all containers
        if not container_name:
            containers, error = list_containers(connection_string)
            if error:
                err = f"Error accessing storage account: {error}"
                logging.error(err)
                # Return HTML error
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Error</title>
                    <style>
                        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
                        .error {{ color: #d13438; background: #fdf2f2; padding: 15px; border-radius: 4px; }}
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h2>Storage Account Error</h2>
                        <p>{err}</p>
                    </div>
                </body>
                </html>
                """
                return func.HttpResponse(
                    error_html,
                    status_code=500,
                    mimetype="text/html"
                )
            
            # Generate HTML for storage account view
            html_output = generate_storage_html(containers, [], [], '', '', connection_string)
            return func.HttpResponse(
                html_output,
                status_code=200,
                mimetype="text/html"
            )
        
        else:
            # List items in specific container
            folders, files, error = list_container_items(connection_string, container_name, path_name)
            
            if error:
                err = f"Error accessing container '{container_name}': {error}"
                logging.error(err)
                # Return HTML error
                error_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Error</title>
                    <style>
                        body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
                        .error {{ color: #d13438; background: #fdf2f2; padding: 15px; border-radius: 4px; }}
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h2>Container Error</h2>
                        <p>{err}</p>
                    </div>
                </body>
                </html>
                """
                return func.HttpResponse(
                    error_html,
                    status_code=404,
                    mimetype="text/html"
                )
            
            # Generate HTML for container view
            html_output = generate_storage_html([], folders, files, container_name, path_name, connection_string)
            return func.HttpResponse(
                html_output,
                status_code=200,
                mimetype="text/html"
            )

    except Exception as ex:
        logging.exception("Unhandled error:")
        # Return HTML error
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <style>
                body {{ font-family: 'Segoe UI', sans-serif; padding: 20px; }}
                .error {{ color: #d13438; background: #fdf2f2; padding: 15px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h2>Unexpected Error</h2>
                <p>{str(ex)}</p>
            </div>
        </body>
        </html>
        """
        return func.HttpResponse(
            error_html,
            status_code=500,
            mimetype="text/html"
        )