from modelscope import snapshot_download

campplus_path = snapshot_download(
    'iic/speech_campplus_sv_zh-cn_16k-common',
    revision='v1.0.0'
)

sensevoice_path = snapshot_download(
    'iic/SenseVoiceSmall',
    revision='master'
)