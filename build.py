# -*- coding: utf-8 -*-
# AI API Hub — PyInstaller 打包脚本

import os
import shutil


def build():
    """执行 PyInstaller 打包流程"""
    work_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(work_dir, 'dist')
    build_dir = os.path.join(work_dir, 'build')

    # 清理旧的构建产物
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)
        print("已清理 dist 目录")
    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)
        print("已清理 build 目录")

    # 自动生成图标（如果不存在）
    icon_path = os.path.join(work_dir, 'icon.ico')
    if not os.path.exists(icon_path):
        print("图标文件不存在，正在生成...")
        try:
            from icon import create_icon
            create_icon()
        except Exception as e:
            print(f"图标生成失败: {e}，将使用默认图标")
            icon_path = None

    sep = os.pathsep

    args = [
        'run.py',
        '--name=AI-API-Hub',
        '--onefile',
        '--noconsole',
        f'--add-data=templates{sep}templates',
        f'--add-data=static{sep}static',
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=sqlite3',
        '--hidden-import=docx',
        '--hidden-import=PyPDF2',
        '--hidden-import=openpyxl',
        '--hidden-import=bs4',
        '--hidden-import=lxml',
        '--hidden-import=requests',
        '--collect-all=flask',
        '--collect-all=flask_cors',
    ]

    if icon_path and os.path.exists(icon_path):
        args.append(f'--icon={icon_path}')

    print("开始打包...")
    import PyInstaller.__main__
    PyInstaller.__main__.run(args)

    exe_path = os.path.join(dist_dir, 'AI-API-Hub.exe')
    print(f"\n打包完成！可执行文件位置: {exe_path}")

    # 复制数据库文件到 dist 目录（如果存在）
    db_src = os.path.join(work_dir, 'ai_api_hub.db')
    if os.path.exists(db_src):
        shutil.copy2(db_src, os.path.join(dist_dir, 'ai_api_hub.db'))
        print("已复制数据库文件到 dist 目录")


if __name__ == '__main__':
    build()
