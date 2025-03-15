from flask import Flask, render_template, request, jsonify
import markdown
import os
from datetime import datetime
import base64
import re
import shutil
from urllib.parse import unquote
from pathlib import Path

app = Flask(__name__)

POSTS_DIR = "posts"
if not os.path.exists(POSTS_DIR):
    os.makedirs(POSTS_DIR)

@app.route('/')
def editor():
    return render_template('editor.html')

@app.route('/preview', methods=['POST'])
def preview():
    content = request.json.get('content', '')
    # Use GitHub-style markdown extensions
    html = markdown.markdown(content, extensions=[
        'markdown.extensions.fenced_code',
        'markdown.extensions.tables',
        'markdown.extensions.codehilite',
        'markdown.extensions.nl2br',
        'markdown.extensions.sane_lists'
    ])
    return jsonify({'html': html})

def save_base64_image(base64_str, post_dir):
    """Save a base64 image to the post directory and return the relative path."""
    # Extract the actual base64 string and file type
    match = re.match(r'data:image/(\w+);base64,(.+)', base64_str)
    if not match:
        return None
    
    img_type, img_data = match.groups()
    
    # Create a filename based on timestamp to ensure uniqueness
    filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{img_type}"
    filepath = os.path.join(post_dir, filename)
    
    # Decode and save the image
    with open(filepath, 'wb') as f:
        f.write(base64.b64decode(img_data))
    
    return filename

@app.route('/save', methods=['POST'])
def save_post():
    data = request.json
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    
    if not title or not content:
        return jsonify({'error': 'Title and content are required'}), 400
    
    # Create a safe directory name from the title
    dir_name = "".join(c for c in title.lower() if c.isalnum() or c in (' ',)).replace(' ', '-')
    post_dir = os.path.join(POSTS_DIR, dir_name)
    
    # If directory exists, add a timestamp to make it unique
    if os.path.exists(post_dir):
        dir_name = f"{dir_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        post_dir = os.path.join(POSTS_DIR, dir_name)
    
    # Create post directory
    os.makedirs(post_dir)
    
    # Process content for images
    def process_image_match(match):
        alt_text = match.group(1)
        image_src = match.group(2)
        
        # Handle base64 images
        if image_src.startswith('data:image'):
            filename = save_base64_image(image_src, post_dir)
            if filename:
                return f'![{alt_text}]({filename})'
            return match.group(0)
        
        # Handle URLs or local file paths
        if image_src.startswith(('http://', 'https://', 'file://')):
            try:
                # For local files, copy them to the post directory
                if image_src.startswith('file://'):
                    src_path = unquote(image_src[7:])
                    if os.path.exists(src_path):
                        ext = os.path.splitext(src_path)[1]
                        filename = f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                        shutil.copy2(src_path, os.path.join(post_dir, filename))
                        return f'![{alt_text}]({filename})'
            except Exception as e:
                print(f"Error processing image {image_src}: {e}")
                return match.group(0)
        
        return match.group(0)
    
    # Update image references in content
    content = re.sub(r'!\[(.*?)\]\((.*?)\)', process_image_match, content)
    
    # Add metadata
    metadata = {
        'title': title,
        'created_at': datetime.now().isoformat(),
        'last_modified': datetime.now().isoformat()
    }
    
    # Save markdown file with metadata as YAML frontmatter
    post_path = os.path.join(post_dir, 'index.md')
    with open(post_path, 'w') as f:
        f.write('---\n')
        for key, value in metadata.items():
            f.write(f'{key}: {value}\n')
        f.write('---\n\n')
        f.write(content)
    
    return jsonify({
        'success': True, 
        'path': os.path.relpath(post_path, POSTS_DIR),
        'directory': dir_name
    })

if __name__ == '__main__':
    app.run(debug=True)
