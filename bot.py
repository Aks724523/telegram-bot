from flask import Flask, request
import telebot, os
from io import BytesIO
from PIL import Image
import insightface
from insightface.app import FaceAnalysis
import numpy as np

TOKEN = os.environ.get('8472666215:AAGvyl6QDquXRbsMKyikzjT_AyQNbSezlxA')
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Initialize face detection model
face_app = FaceAnalysis(name='buffalo_l')
face_app.prepare(ctx_id=-1, det_size=(640, 640))  # Use -1 for CPU, 0 for GPU

# Load the face swap model
swapper = insightface.model_zoo.get_model('inswapper_128.onnx', download=True)

user_data = {}

@app.route('/webhook', methods=['POST'])
def webhook():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "OK", 200

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
        """Welcome to Face Swap Bot! 🎭

Instructions:
1. Send your face photo (the one to be swapped).
2. Then send the target photo (where you want your face to appear).
3. The bot will send back the swapped image.

Commands:
/start - Start the bot
/reset - Reset and upload new photos"""
    )

@bot.message_handler(commands=['reset'])
def reset_user(message):
    user_id = message.from_user.id
    user_data.pop(user_id, None)
    bot.reply_to(message, "🔄 Reset complete! Please send a new photo.")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    user_id = message.from_user.id
    
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    image = Image.open(BytesIO(downloaded_file))
    image.thumbnail((1024, 1024))

    if user_id not in user_data:
        user_data[user_id] = {'source_image': image}
        bot.reply_to(message, "✅ Source image saved! Now send the target photo.")
    else:
        bot.reply_to(message, "⏳ Processing... Please wait.")
        source_image = user_data[user_id]['source_image']
        target_image = image

        try:
            swapped_image = perform_face_swap(source_image, target_image)
            bio = BytesIO()
            swapped_image.save(bio, 'PNG')
            bio.seek(0)
            bot.send_photo(message.chat.id, bio, caption="✅ Face swap complete! Use /reset to try again.")
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {e}\nUse /reset and try again.")
        finally:
            user_data.pop(user_id, None)

def perform_face_swap(source_img, target_img):
    source_np = np.array(source_img)
    target_np = np.array(target_img)
    
    source_faces = face_app.get(source_np)
    if len(source_faces) == 0:
        raise Exception("No face detected in the source image.")
    source_face = source_faces[0]
    
    target_faces = face_app.get(target_np)
    if len(target_faces) == 0:
        raise Exception("No face detected in the target image.")
    
    result = target_np.copy()
    for target_face in target_faces:
        result = swapper.get(result, target_face, source_face, paste_back=True)
    
    return Image.fromarray(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)