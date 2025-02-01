from flask import Flask, request, send_file
import ffmpeg
import os

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_video():
    """Receives video, applies FFmpeg, and returns output."""
    if 'video' not in request.files:
        return {"error": "No video uploaded"}, 400

    file = request.files['video']
    input_path = f"/tmp/{file.filename}"
    output_path = f"/tmp/processed_{file.filename}"
    file.save(input_path)

    # Apply FFmpeg: Adding text to the video
    ffmpeg.input(input_path).output(output_path, vf="drawtext=text='Hello World':x=10:y=10:fontsize=24:fontcolor=white").run()

    return send_file(output_path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
