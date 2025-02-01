from flask import Flask, request, send_file, jsonify
import ffmpeg
import os
import traceback
import uuid

app = Flask(__name__)

@app.route('/process', methods=['POST'])
def process_video():
    """Receives a video, applies FFmpeg processing, and returns the output."""
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video uploaded"}), 400

        # Get the uploaded video file
        file = request.files['video']

        # Define paths
        input_path = os.path.join(os.getcwd(), file.filename)

        # Generate a unique filename for the output (to prevent overwriting)
        output_filename = f"processed_{uuid.uuid4().hex}_{file.filename}"
        output_path = os.path.join(os.getcwd(), output_filename)

        # Save the video to the server
        file.save(input_path)

        # Ensure the file was saved
        if not os.path.exists(input_path):
            return jsonify({"error": f"Failed to save the file: {input_path}"}), 500

        # Apply FFmpeg: Add text to the video
        print(f"Running FFmpeg on {input_path}...")

        # Run FFmpeg and capture output and errors
        try:
            ffmpeg.input(input_path).output(output_path, vf="drawtext=text='Hello World':x=10:y=10:fontsize=24:fontcolor=white").run(cmd='ffmpeg', capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            print(f"FFmpeg error: {e.stderr.decode()}")
            return jsonify({"error": "FFmpeg failed to process the video."}), 500

        # Check if the output file was created
        if not os.path.exists(output_path):
            return jsonify({"error": "FFmpeg failed to process the video."}), 500

        # Return the processed video as an attachment
        return send_file(output_path, as_attachment=True)

    except Exception as e:
        # Print stack trace for debugging
        print(f"Error processing video: {e}")
        print(traceback.format_exc())
        return jsonify({"error": "Server error while processing the video."}), 500

if __name__ == '__main__':
    # Run the Flask app on all available IP addresses (to allow external requests)
    app.run(host='0.0.0.0', port=8080)
