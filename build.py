import os
import PyInstaller.__main__

def build_app():
    PyInstaller.__main__.run([
        'main4.py',
        '--onefile',
        '--windowed',
        '--noconsole',
        '--name=校园网自动认证工具',
        '--add-data=config.json;.',
        '--add-data=log.txt;.',
        '--icon=gxnu.ico',  # 如果有图标文件
        '--clean',
        '--noconfirm'
    ])

if __name__ == '__main__':
    build_app()