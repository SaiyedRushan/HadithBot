from flask import Flask
import os
import threading
app = Flask('')

@app.route('/')
def home():
    return "Hello. I am alive!"

def run_bot(): 
    os.system('python bot.py')

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    app.run(host='0.0.0.0', port=8080)
