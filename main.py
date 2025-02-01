from flask import Flask, request, send_file
import subprocess
import tempfile
import os
import traceback

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_video():
    try:
        if 'video' not in request.files:
            return {"error": "No video file provided"}, 400
        
        video_file = request.files['video']
        
        with tempfile.NamedTemporaryFile(delete=True, suffix='.mp4') as input_tmp, \
             tempfile.NamedTemporaryFile(delete=True, suffix='.mp4') as output_tmp:
            
            input_tmp.write(video_file.read())
            input_tmp.flush()
            
            command = [
                'ffmpeg', '-y', '-i', input_tmp.name, 
                '-vf', "drawtext=text='Hello!':fontcolor=white:fontsize=24:x=10:y=10", 
                '-c:a', 'copy', output_tmp.name
            ]
            
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            if result.returncode != 0:
                print("FFmpeg Error:", result.stderr.decode())  # Print FFmpeg error
                return {"error": "FFmpeg processing failed", "details": result.stderr.decode()}, 500
            
            return send_file(output_tmp.name, mimetype='video/mp4', as_attachment=True, download_name='output.mp4')
    
    except Exception as e:
        print("Flask Error:", traceback.format_exc())  # Print Python error
        return {"error": "Internal Server Error", "details": str(e)}, 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
