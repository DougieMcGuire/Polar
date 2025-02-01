from flask import Flask, request, send_file, jsonify
import subprocess
import tempfile
import os
import logging
import re
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# Define safe FFmpeg filters and options
SAFE_FILTERS = {
    'drawtext', 'scale', 'crop', 'rotate', 'transpose', 'hflip', 'vflip',
    'colorbalance', 'eq', 'hue', 'overlay', 'pad', 'trim', 'setpts',
    'volume', 'afade', 'areverse', 'atempo', 'fade', 'colorize', 'format',
    'fps', 'reverse', 'setdar', 'setsar', 'sharpen', 'unsharp', 'zoompan'
}

SAFE_CODECS = {
    'libx264', 'libx265', 'aac', 'libmp3lame', 'libvorbis', 'libvpx', 
    'libvpx-vp9', 'libopus', 'copy'
}

def sanitize_ffmpeg_command(command_str):
    """
    Sanitize and validate FFmpeg command string
    Returns (is_safe, sanitized_command or error_message)
    """
    try:
        # Split command while preserving quoted strings
        parts = []
        current = []
        in_quotes = False
        i = 0
        
        while i < len(command_str):
            if command_str[i] in ['"', "'"]:
                in_quotes = not in_quotes
                i += 1
                continue
            elif command_str[i].isspace() and not in_quotes:
                if current:
                    parts.append(''.join(current))
                    current = []
                i += 1
                continue
            current.append(command_str[i])
            i += 1
            
        if current:
            parts.append(''.join(current))

        # Basic security checks
        for part in parts:
            # Check for suspicious patterns
            if any(pattern in part.lower() for pattern in [
                ';', '&&', '||', '|', '>', '<', '$', '`', '$(', '${',
                'rm ', 'mv ', 'cp ', '/bin/', '/etc/', '/dev/', '/sys/',
                'sudo', 'bash', 'sh '
            ]):
                return False, "Command contains forbidden characters or patterns"

            # Validate filter names if -vf or -filter:v is used
            if part.startswith('filter:') or part.startswith('vf='):
                filter_str = part.split('=', 1)[1]
                filter_names = re.findall(r'([a-zA-Z]+)(?:=|:|\,|\s|$)', filter_str)
                for filter_name in filter_names:
                    if filter_name not in SAFE_FILTERS:
                        return False, f"Filter '{filter_name}' is not allowed"

            # Validate codec names
            if part.startswith('c:') or part.startswith('codec:'):
                codec = part.split('=', 1)[1]
                if codec not in SAFE_CODECS:
                    return False, f"Codec '{codec}' is not allowed"

        return True, parts

    except Exception as e:
        logger.error(f"Error sanitizing command: {str(e)}")
        return False, "Invalid command format"

def process_with_ffmpeg(input_path, output_path, custom_command=None):
    """Process video with FFmpeg using optional custom command"""
    try:
        if custom_command:
            is_safe, command_parts = sanitize_ffmpeg_command(custom_command)
            if not is_safe:
                return False, f"Invalid command: {command_parts}"
            
            # Build complete command
            command = ['ffmpeg', '-y', '-i', input_path]
            command.extend(command_parts)
            command.append(output_path)
        else:
            # Default command as fallback
            command = [
                'ffmpeg', '-y', '-i', input_path,
                '-vf', "drawtext=text='Hello!':fontcolor=white:fontsize=24:x=10:y=10:box=1:boxcolor=black@0.5",
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                '-c:a', 'aac', '-movflags', '+faststart',
                output_path
            ]

        logger.info(f"Running FFmpeg command: {' '.join(command)}")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Monitor FFmpeg process
        while True:
            stderr_line = process.stderr.readline()
            if not stderr_line and process.poll() is not None:
                break
            if stderr_line:
                logger.info(f"FFmpeg: {stderr_line.strip()}")
        
        return_code = process.wait()
        
        if return_code != 0:
            _, stderr = process.communicate()
            return False, stderr
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return False, "Output file is missing or empty"
            
        return True, None
        
    except Exception as e:
        logger.error(f"Exception during FFmpeg processing: {str(e)}")
        return False, str(e)

@app.route('/')
def home():
    """API documentation homepage"""
    return jsonify({
        "status": "active",
        "usage": {
            "endpoint": "POST /process",
            "content-type": "multipart/form-data",
            "fields": {
                "video": "Video file to process",
                "command": "(Optional) FFmpeg command string"
            },
            "supported_formats": ["mp4", "mov", "avi"],
            "max_size": "200MB",
            "safe_filters": list(SAFE_FILTERS),
            "safe_codecs": list(SAFE_CODECS),
            "example_commands": [
                "-vf scale=720:-1 -c:v libx264 -preset faster -crf 23",
                "-vf rotate=45 -c:v libx264 -c:a copy",
                "-vf colorbalance=rs=0.5 -c:v libx264"
            ]
        }
    })

@app.route('/process', methods=['POST'])
def process_video():
    """Process video endpoint with custom command support"""
    logger.info("Received video processing request")
    
    if 'video' not in request.files:
        return jsonify({
            "error": "No video file provided",
            "details": "Include a video file in the 'video' field"
        }), 400
    
    video_file = request.files['video']
    custom_command = request.form.get('command')
    
    if video_file.filename == '':
        return jsonify({
            "error": "No filename provided",
            "details": "Empty filename"
        }), 400
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'input.mp4')
            output_path = os.path.join(temp_dir, 'output.mp4')
            
            logger.info(f"Saving input file to {input_path}")
            video_file.save(input_path)
            
            if not os.path.exists(input_path):
                return jsonify({
                    "error": "File save failed",
                    "details": "Could not save uploaded file"
                }), 500
            
            logger.info("Starting FFmpeg processing")
            success, error_message = process_with_ffmpeg(input_path, output_path, custom_command)
            
            if not success:
                return jsonify({
                    "error": "FFmpeg processing failed",
                    "details": error_message
                }), 500
            
            logger.info("FFmpeg processing completed, sending file")
            return send_file(
                output_path,
                mimetype='video/mp4',
                as_attachment=True,
                download_name='processed_video.mp4'
            )
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
