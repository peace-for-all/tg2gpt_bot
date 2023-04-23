import os
import logging
import tempfile
# import subprocess
# from deepspeech import Model
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackContext, Filters
from pydub import AudioSegment
import struct
import openai
import io
from dotenv import load_dotenv

# Keys!
load_dotenv('.env')
openai.api_key = os.environ.get('OPENAI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TESTING_USER_NAME = os.environ.get('TESTING_USER_NAME')

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def voice_to_text(audio_file):
    # Load audio file and convert it to a 16-bit PCM WAV format
    audio = AudioSegment.from_file(audio_file, format="ogg")
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    wav_data = io.BytesIO()
    audio.export(wav_data, format="wav")

    # Add the WAV file header
    wav_data = bytearray(wav_data.getvalue())
    riff = struct.pack('<4sI4s', b'RIFF', len(wav_data) + 8, b'WAVE')
    fmt = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, 16000, 32000, 2, 16)
    data = struct.pack('<4sI', b'data', len(wav_data))
    wav_data = bytearray(riff) + bytearray(fmt) + bytearray(data) + wav_data[4:]

    # Play?
    # subprocess.Popen(["aplay", "-"], stdin=subprocess.PIPE).communicate(input=bytes(wav_data))

    # Write wav into file (bcs speech recog needs it)
    with open("audio_data.wav", "wb") as f:
        f.write(wav_data)

    import speech_recognition as sr
    r = sr.Recognizer()
    # with sr.Microphone() as source:
    #     audio_file = r.record(source, duration=5)
    with sr.AudioFile("audio_data.wav") as source:
        audio_data = r.record(source)

    transcript = ""

    try:
        transcript = r.recognize_google(audio_data)
        logger.info("You said: " + transcript)
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))

    # delete audio_data.wav
    os.remove("audio_data.wav")

    return transcript


def send_to_chat_gpt(text):
    prompt = f"{text}"
    logger.info(f"Sent to ChatGPT: {prompt}")
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=2048,
        n=1,
        stop=None,
        temperature=0.5,
    )
    # response = openai.Completion.create(
    #     engine="text-davinci-003",
    #     prompt=prompt,
    #     max_tokens=1024,
    #     n=1,
    #     stop=None,
    #     temperature=1,
    #     top_p=1.0,
    #     presence_penalty=0.2,
    #     frequency_penalty=0.2
    #     # repetition_penalty=1.0
    # )
    return response.choices[0].text.strip()


# Function to handle voice messages
def handle_voice_message(update: Update, context: CallbackContext):
    logger.info("Received a voice message")

    sender_username = update.message.from_user.username
    # if sender_username != "walsk":  # wx REMOVE THIS LINE FROM CODE B4 RELEASE
    #     logger.info(f"Ignoring message from user '{sender_username}'")
    #     return

    voice = update.message.voice
    file_id = voice.file_id
    new_file = context.bot.get_file(file_id)

    with tempfile.NamedTemporaryFile(suffix=".ogg") as temp_file:
        logger.info("Downloading the voice message")
        new_file.download(out=temp_file)
        temp_file.flush()

        # logger.info("Playing the original voice message")
        # subprocess.run(["ffplay", "-nodisp", "-autoexit", temp_file.name], stdout=subprocess.PIPE,
        #                stderr=subprocess.PIPE)

        logger.info("Transcribing the voice message")
        transcript = voice_to_text(temp_file.name)
        # logger.info(f"Transcript: {transcript}")
        update.message.reply_text(f"(You've asked: {transcript})")

    logger.info("Sending the text to ChatGPT and getting a response")
    response = send_to_chat_gpt(transcript)
    logger.info("Response: " + response)

    logger.info("Sending the response as a text message")
    update.message.reply_text(response)
    if transcript == "" or not response:
        update.message.reply_text("voice2text failed, retry?")
    # else:
    #     update.message.reply_text(transcript)

    # wx delete after use
    def text_to_speech(text, out_file):
        from gtts import gTTS
        tts = gTTS(response, lang='en')
        tts.save(out_file)
        return out_file

    text_to_speech(response, "response.mp3")
    update.message.reply_voice(open("response.mp3", "rb"))

    # from pydub import AudioSegment
    # sound = AudioSegment.from_mp3("myfile.mp3")
    # sound.export("myfile.wav", format="wav")


# Function to handle text messages
def handle_text_message(update: Update, context: CallbackContext):
    sender_username = update.message.from_user.username
    # if sender_username != TESTING_USER_NAME:
    #     logger.info(f"Ignoring message from user '{sender_username}'")
    #     return

    input_text = update.message.text
    response = send_to_chat_gpt(input_text)
    logger.info(f"Response: {response}")
    update.message.reply_text(response)
    # update.message.reply_text('I am a bot, please talk to me!')


def main():
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(MessageHandler(Filters.voice, handle_voice_message))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_text_message))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
