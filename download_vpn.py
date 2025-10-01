import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# 添加临时环境变量
current_dir = os.path.dirname(os.path.abspath(__file__))
relative_path = "bin"
absolute_path = os.path.join(current_dir, relative_path)
os.environ["PATH"] = absolute_path + os.pathsep + os.environ.get("PATH", "")

model_dir = 'models'

from config import Global

# 下载embedding模型
from huggingface_hub import snapshot_download
embedding_path = os.path.join(model_dir, 'embedding')
snapshot_download(
    repo_id=Global.embedding,
    local_dir=embedding_path,
    local_dir_use_symlinks=False
)

# 下载UVR5模型
from audio_separator.separator import Separator
separator = Separator(model_file_dir=model_dir+'/UVR')
# 人声分离
separator.load_model(model_filename='UVR-MDX-NET-Inst_HQ_3.onnx')
# 和声分离
separator.load_model(model_filename='UVR_MDXNET_KARA_2.onnx')