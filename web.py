import json
import logging
from flask import Flask, send_from_directory

live2d_port = 5000
app = Flask(__name__, static_folder='.')
# logging.getLogger('werkzeug').setLevel(logging.ERROR)

# 配置类
class Config:
    def __init__(self):
        self.background_width = 1920
        self.background_height = 1080
        self.canvas_width = "60%"
        self.canvas_margin = "50px"

config = Config()

def generate_html():
    """动态生成HTML内容"""
    return f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/x-icon" href="assets/icons/icon.ico" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      body {{
        background-image: url('assets/bg/bg.jpg');
        background-size: {config.background_width}px {config.background_height}px;
        background-repeat: no-repeat;
        background-position: center center;
        background-attachment: fixed;
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100vh;
      }}
      #canvas2 {{
        width: {config.canvas_width};
        height: auto;
        margin: {config.canvas_margin} auto;
        display: block;
        background-color: transparent;
      }}
    </style>
    <script src="assets/live2d_core/live2dcubismcore.min.js"></script>
    <script src="assets/live2d_core/live2d.min.js"></script>
    <script src="assets/live2d_core/pixi.min.js"></script>
    <title>Ciallo～(∠・ω< )⌒★</title>
    <script type="module" crossorigin src="assets/live2d.js"></script>
  </head>
  <body>
    <div id="app"></div>
    <canvas id="canvas2"></canvas>
  </body>
</html>
"""

@app.route('/')
def index():
    return generate_html()

@app.route('/assets/<path:path>')
def serve_static(path):
    return send_from_directory('assets', path)

@app.route('/api/get_mouth_y')
def read_txt():
    return json.dumps({"y": 0})

def run_live2d():
    app.run(port=live2d_port, host="0.0.0.0")

if __name__ == '__main__':
    run_live2d()