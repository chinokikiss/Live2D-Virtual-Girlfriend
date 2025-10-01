from modelscope import snapshot_download

model_dir = 'models'

campplus_path = snapshot_download(
    'iic/speech_campplus_sv_zh-cn_16k-common',
    revision='v1.0.0',
    cache_dir=model_dir
)

sensevoice_path = snapshot_download(
    'iic/SenseVoiceSmall',
    revision='master',
    cache_dir=model_dir
)