from flask import Flask, request, send_file, jsonify
import subprocess
import tempfile
import os
import logging
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Increase maximum file size to 200MB
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

def process_with_ffmpeg(input_path, output_path):
    """Process video with FFmpeg using more reliable settings"""
    try:
        # First, probe the input file
        probe_command = [
            'ffmpeg',
            '-i', input_path,
            '-v', 'error'
        ]
        
        probe_result = subprocess.run(
            probe_command,
            capture_output=True,
            text=True
        )
        
        if probe_result.stderr:
            logger.warning(f"FFmpeg probe warnings: {probe_result.stderr}")
        
        # Main FFmpeg command with more reliable settings
        command = [
            'ffmpeg',
            '-y',  # Overwrite output
            '-i', input_path,
            '-vf', "drawtext=text='Hello!':fontcolor=white:fontsize=24:x=10:y=10:box=1:boxcolor=black@0.5",
            '-c:v', 'libx264',  # Explicitly set video codec
            '-preset', 'ultrafast',  # Faster encoding
            '-crf', '23',  # Balance quality/size
            '-c:a', 'aac',  # Explicitly set audio codec
            '-movflags', '+faststart',  # Web optimized
            '-max_muxing_queue_size', '1024',  # Prevent muxing errors
            output_path
        ]
        
        logger.info(f"Running FFmpeg command: {' '.join(command)}")
        
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Monitor the FFmpeg process
        while True:
            stderr_line = process.stderr.readline()
            if not stderr_line and process.poll() is not None:
                break
            if stderr_line:
                logger.info(f"FFmpeg: {stderr_line.strip()}")
        
        return_code = process.wait()
        
        if return_code != 0:
            _, stderr = process.communicate()
            logger.error(f"FFmpeg failed with return code {return_code}: {stderr}")
            return False, stderr
        
        # Verify output file exists and has size
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return False, "Output file is missing or empty"
            
        return True, None
        
    except Exception as e:
        logger.error(f"Exception during FFmpeg processing: {str(e)}")
        return False, str(e)

@app.route('/')
def home():
    """Basic homepage with API instructions"""
    return jsonify({
        "status": "active",
        "usage": {
            "endpoint": "POST /process",
            "content-type": "multipart/form-data",
            "field": "video",
            "supported_formats": ["mp4", "mov", "avi"],
            "max_size": "200MB"
        }
    })

@app.route('/process', methods=['POST'])
def process_video():
    """Process video endpoint with improved error handling"""
    logger.info("Received video processing request")
    
    if 'video' not in request.files:
        return jsonify({
            "error": "No video file provided",
            "details": "Include a video file in the 'video' field"
        }), 400
    
    video_file = request.files['video']
    
    if video_file.filename == '':
        return jsonify({
            "error": "No filename provided",
            "details": "Empty filename"
        }), 400
    
    try:
        # Create temporary directory for processing
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
            success, error_message = process_with_ffmpeg(input_path, output_path)
            
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
