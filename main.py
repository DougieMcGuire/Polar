from flask import Flask, request, send_file, jsonify
import subprocess
import tempfile
import os
import logging
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Increase maximum file size to 100MB (adjust as needed)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

def is_ffmpeg_installed():
    """Check if FFmpeg is installed and accessible"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except FileNotFoundError:
        return False

def process_with_ffmpeg(input_path, output_path):
    """Process video with FFmpeg and provide detailed error handling"""
    command = [
        'ffmpeg',
        '-y',  # Overwrite output file if it exists
        '-i', input_path,
        '-vf', "drawtext=text='Hello!':fontcolor=white:fontsize=24:x=10:y=10",
        '-c:a', 'copy',
        output_path
    ]
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True  # This will raise CalledProcessError if FFmpeg fails
        )
        return True, None
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg Error: {e.stderr}")
        return False, e.stderr

@app.route('/')
def home():
    """Basic homepage with API instructions"""
    return jsonify({
        "status": "active",
        "usage": "POST /process with a video file in the 'video' field",
        "ffmpeg_available": is_ffmpeg_installed()
    })

@app.route('/process', methods=['POST'])
def process_video():
    """Process video endpoint with comprehensive error handling"""
    logger.info("Received video processing request")
    
    # Check if FFmpeg is installed
    if not is_ffmpeg_installed():
        logger.error("FFmpeg not found on system")
        return jsonify({
            "error": "FFmpeg not installed",
            "details": "Server configuration error"
        }), 500

    # Validate request
    if 'video' not in request.files:
        logger.warning("No video file in request")
        return jsonify({
            "error": "No video file provided",
            "details": "Include a video file in the 'video' field"
        }), 400
    
    video_file = request.files['video']
    
    # Validate filename
    if video_file.filename == '':
        logger.warning("Empty filename provided")
        return jsonify({
            "error": "No filename provided",
            "details": "Empty filename"
        }), 400

    try:
        # Create temporary directory to handle files
        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = os.path.join(temp_dir, 'input.mp4')
            output_path = os.path.join(temp_dir, 'output.mp4')
            
            # Save input file
            logger.info("Saving input file")
            video_file.save(input_path)
            
            # Process with FFmpeg
            logger.info("Processing video with FFmpeg")
            success, error_message = process_with_ffmpeg(input_path, output_path)
            
            if not success:
                return jsonify({
                    "error": "FFmpeg processing failed",
                    "details": error_message
                }), 500
            
            # Send processed file
            logger.info("Sending processed file")
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
    # Check FFmpeg availability on startup
    if not is_ffmpeg_installed():
        logger.warning("FFmpeg not found! Please install FFmpeg before running the server.")
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
