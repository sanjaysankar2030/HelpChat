let isRecording = false;
let recognition;

$(document).ready(function () {
    $(".submit-btn").click(function () {
        sendText();
    });

    $("#voice-btn").click(function () {
        if (!isRecording) {
            startSpeechRecognition();
        } else {
            stopSpeechRecognition();
        }
    });

    $("#stop-btn").click(function () {
        stopAudioPlayback();
    });
});

function startSpeechRecognition() {
    if (!("webkitSpeechRecognition" in window)) {
        alert("Speech recognition is not supported in this browser.");
        return;
    }

    recognition = new webkitSpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = function () {
        isRecording = true;
        $("#voice-btn").text("⏹");
    };

    recognition.onresult = function (event) {
        let transcript = event.results[0][0].transcript;
        $("#user_input").val(transcript);  // Fill input box with recognized speech
        sendText();
    };

    recognition.onerror = function (event) {
        console.error("Speech recognition error:", event.error);
    };

    recognition.onend = function () {
        isRecording = false;
        $("#voice-btn").text("🎤");
    };

    recognition.start();
}

function stopSpeechRecognition() {
    if (recognition) {
        recognition.stop();
        isRecording = false;
        $("#voice-btn").text("🎤");
    }
}

function sendText() {
    let user_input = $("#user_input").val().trim();
    if (user_input === "") return;

    $.post("/ask", { user_input: user_input }, function (data) {
        $("#answer-text").val(data.answer);
        waitForAudioAndPlay();
    });
}

function waitForAudioAndPlay() {
    let checkAudio = setInterval(function () {
        $.get("/audio_status", function (data) {
            if (data.ready) {
                clearInterval(checkAudio);
                playAudioResponse();
            }
        });
    }, 500);
}

function playAudioResponse() {
    let audio = $("#audio")[0];
    audio.src = "/speak?" + new Date().getTime(); // Prevent caching
    audio.style.display = "block";
    $("#stop-btn").show();
    audio.play();
}

function stopAudioPlayback() {
    let audio = $("#audio")[0];
    audio.pause();
    audio.currentTime = 0;
    audio.style.display = "none";
    $("#stop-btn").hide();
}
