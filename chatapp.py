from flask import Flask, render_template, request, jsonify, send_file
from ollama import chat
from gtts import gTTS
from pydub import AudioSegment
import io
import threading
import os

app = Flask(__name__)

# Initialize conversation history and audio buffer
conversation_history = []
latest_audio_buffer = None
buffer_lock = threading.Lock()
audio_ready = threading.Event()


@app.route("/", methods=["GET"])
def index():
    return render_template("home.html")


@app.route("/ask", methods=["POST"])
def ask():
    global conversation_history, latest_audio_buffer, audio_ready

    # Reset audio_ready event before processing
    audio_ready.clear()

    user_input = request.form["user_input"]

    # Append user input to conversation history
    conversation_history.append({"role": "user", "content": user_input})

    # Keep only the last two interactions
    if len(conversation_history) > 4:
        conversation_history = conversation_history[-4:]

    # Generate chatbot response
    response = chat(
        model="smollm2:360m",
        messages=conversation_history,
    )
    answer = response["message"]["content"]

    # Append model response to conversation history
    conversation_history.append({"role": "assistant", "content": answer})

    # Start the TTS generation in a separate thread and join it before responding
    tts_thread = threading.Thread(target=generate_tts, args=(answer,))
    tts_thread.start()
    tts_thread.join()  # Ensure TTS finishes before returning response

    return jsonify(answer=answer)


def generate_tts(text):
    global latest_audio_buffer, audio_ready

    try:
        # Clear the previous audio buffer before generating new audio
        with buffer_lock:
            latest_audio_buffer = None
            audio_ready.clear()

        tts = gTTS(text, lang="en")
        mp3_fp = io.BytesIO()
        tts.write_to_fp(mp3_fp)

        # Convert mp3 to wav for better browser compatibility
        mp3_fp.seek(0)
        sound = AudioSegment.from_mp3(mp3_fp)
        wav_fp = io.BytesIO()
        sound.export(wav_fp, format="wav")

        # Store the raw bytes safely
        with buffer_lock:
            latest_audio_buffer = wav_fp.getvalue()
            audio_ready.set()  # Signal that audio is ready

    except Exception as e:
        print(f"Error in TTS generation: {e}")
        audio_ready.set()  # Ensure event is set even on failure


@app.route("/audio_status", methods=["GET"])
def audio_status():
    return jsonify(ready=audio_ready.is_set())


@app.route("/speak", methods=["GET"])
def speak():
    global latest_audio_buffer

    with buffer_lock:
        if latest_audio_buffer:
            buffer = io.BytesIO(latest_audio_buffer)
            return send_file(buffer, as_attachment=False, mimetype="audio/wav")
        else:
            return "No audio available", 404


# Ensure templates directory exists
os.makedirs("templates", exist_ok=True)

# Create home.html template with simplified UI
with open("templates/home.html", "w") as f:
    f.write(
        """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Input and Display</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">
    <style>
        #loading-spinner {
            display: none;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 1.5em;
            color: #000;
        }
        #stop-btn {
            width: 60px;
            height: 40px;
            border: none;
            border-radius: 8px;
            background-color: #ffb6c1;
            cursor: pointer;
            color: #333;
            display: none;
        }
        #audio {
            display: none;
        }
    </style>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
    <div id="main-content">
        <div id="input-div">
            <form id="text-form">
                <div class="input-group">
                    <input type="text" id="user_input" name="user_input" placeholder="Ask questions here">
                    <button type="submit" class="submit-btn" name="submit-btn">Submit</button>
                </div>
            </form>
        </div>
        
        <div id="output-div">
            <textarea rows="4" readonly placeholder="Answers here" id="answer-text"></textarea>
        </div>
        <button type="button" id="stop-btn">Stop Audio</button>
        <div id="loading-spinner">Loading...</div>
    </div>
    <audio id="audio" controls></audio>
    <script>
        $(document).ready(function() {
            let audioPollingInterval;
            let checkAudioStarted = false;
            
            $('#text-form').on('submit', function(event) {
                event.preventDefault();
                const user_input = $('#user_input').val();
                if (!user_input.trim()) return;
                
                $('#loading-spinner').show();
                checkAudioStarted = false;
                
                // Stop any currently playing audio
                const audioElement = document.getElementById('audio');
                audioElement.pause();
                $('#stop-btn').hide();
                
                $.ajax({
                    url: '/ask',
                    method: 'POST',
                    data: { user_input: user_input },
                    success: function(response) {
                        $('#loading-spinner').hide();
                        $('#answer-text').val(response.answer);
                        $('#user_input').val('');
                        
                        // Start polling for audio immediately
                        checkAudioStarted = true;
                        startAudioPolling();
                    },
                    error: function() {
                        $('#loading-spinner').hide();
                        $('#answer-text').val('Error processing your request.');
                    }
                });
            });
            
            function startAudioPolling() {
                // Clear any existing interval
                if (audioPollingInterval) {
                    clearInterval(audioPollingInterval);
                }
                
                let attempts = 0;
                // Check if audio is ready every 100ms
                audioPollingInterval = setInterval(function() {
                    attempts++;
                    // Stop after 100 attempts (10 seconds)
                    if (attempts > 100) {
                        clearInterval(audioPollingInterval);
                        return;
                    }
                    
                    $.ajax({
                        url: '/audio_status',
                        method: 'GET',
                        success: function(response) {
                            if (response.ready && checkAudioStarted) {
                                clearInterval(audioPollingInterval);
                                playAudio();
                            }
                        }
                    });
                }, 100);
            }
            
            function playAudio() {
                // Add a timestamp to prevent caching
                const timestamp = new Date().getTime();
                const audioElement = document.getElementById('audio');
                audioElement.src = '/speak?t=' + timestamp;
                audioElement.play().catch(function(error) {
                    console.log("Error playing audio:", error);
                });
                $('#stop-btn').show();
            }
            
            $('#stop-btn').on('click', function() {
                const audioElement = document.getElementById('audio');
                audioElement.pause();
                audioElement.currentTime = 0;
                $('#stop-btn').hide();
            });
            
            // Hide stop button when audio finishes playing
            document.getElementById('audio').addEventListener('ended', function() {
                $('#stop-btn').hide();
            });
        });
    </script>
</body>
</html>"""
    )

if __name__ == "__main__":
    app.run(debug=True)
