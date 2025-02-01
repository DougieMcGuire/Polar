import io
import subprocess
from flask import Flask, request, send_file

app = Flask(__name__)

@app.route('/edit-video', methods=['POST'])
def edit_video():
    # Step 1: Get the video file from the request
    file = request.files.get('video')
    if file is None:
        return "No video file provided", 400

    # Step 2: Read the file into memory
    video_input = io.BytesIO(file.read())
    
    # Step 3: Use FFmpeg to edit the video (as an example, we'll just add a watermark)
    output = io.BytesIO()
    command = [
        'ffmpeg',
        '-i', 'pipe:0',  # input from stdin (pipe)
        '-vf', "drawtext=text='Watermark':fontcolor=white@0.5:fontsize=24:x=10:y=10",  # example filter to add watermark
        '-f', 'mp4',  # output format
        'pipe:1'  # output to stdout (pipe)
    ]
    
    # Step 4: Run FFmpeg process
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = process.communicate(input=video_input.read())
    
    # Step 5: Handle any errors
    if process.returncode != 0:
        return f"Error in video processing: {err.decode()}", 500

    # Step 6: Prepare the edited video for response
    output.write(out)
    output.seek(0)
    
    # Step 7: Send the edited video back as a response
    return send_file(output, mimetype='video/mp4', as_attachment=True, download_name='edited_video.mp4')

if __name__ == '__main__':
    app.run(debug=True)
