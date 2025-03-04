from flask import Flask, render_template, request, jsonify, send_file
from ollama import chat
from gtts import gTTS
import os
import threading

app = Flask(__name__)

# Initialize conversation history
conversation_history = []
AUDIO_FILE = "response.wav"
audio_ready = threading.Event()
audio_lock = threading.Lock()


def delete_old_audio():
    if os.path.exists(AUDIO_FILE):
        os.remove(AUDIO_FILE)


def generate_tts(text):
    global audio_ready
    try:
        with audio_lock:
            delete_old_audio()
            tts = gTTS(text, lang="en")
            tts.save(AUDIO_FILE)
            audio_ready.set()
    except Exception as e:
        print(f"Error in TTS generation: {e}")
        audio_ready.clear()


@app.route("/", methods=["GET"])
def index():
    return render_template("home.html")


@app.route("/ask", methods=["POST"])
def ask():
    global conversation_history, audio_ready

    # Reset audio flag before generating new response
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

    # Generate TTS synchronously to ensure audio is ready before response
    generate_tts(answer)

    return jsonify(answer=answer)


@app.route("/audio_status", methods=["GET"])
def audio_status():
    return jsonify(ready=audio_ready.is_set())


@app.route("/speak", methods=["GET"])
def speak():
    with audio_lock:
        if os.path.exists(AUDIO_FILE) and audio_ready.is_set():
            return send_file(AUDIO_FILE, as_attachment=False, mimetype="audio/wav")
        else:
            return "No audio available", 404


if __name__ == "__main__":
    app.run(debug=True)
