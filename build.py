# -*- coding: utf-8 -*-
# AI API Hub — PyInstaller 打包脚本
# 将整个应用打包为单个 Windows .exe 可执行文件

import os          # 操作系统接口，用于路径处理和目录操作
import shutil      # 高级文件操作，用于清理构建目录


def build():
    """执行 PyInstaller 打包流程"""

    # 获取当前脚本所在目录（项目根目录）
    work_dir = os.path.dirname(os.path.abspath(__file__))

    # 构建输出目录路径
    dist_dir = os.path.join(work_dir, 'dist')       # 打包输出目录
    build_dir = os.path.join(work_dir, 'build')     # PyInstaller 构建临时目录

    # 清理旧的构建产物
    if os.path.exists(dist_dir):
        shutil.rmtree(dist_dir)                      # 删除旧的 dist 目录
        print("已清理 dist 目录")

    if os.path.exists(build_dir):
        shutil.rmtree(build_dir)                     # 删除旧的 build 目录
        print("已清理 build 目录")

    # 自动调用 icon.py 生成应用图标（如果图标不存在）
    icon_path = os.path.join(work_dir, 'icon.ico')
    if not os.path.exists(icon_path):
        print("图标文件不存在，正在生成...")
        try:
            from icon import create_icon             # 导入图标生成函数
            create_icon()                            # 生成图标
        except Exception as e:
            print(f"图标生成失败: {e}，将使用默认图标")
            icon_path = None                         # 清空图标路径，不使用图标

    # 使用 os.pathsep 作为分隔符（Windows 为 ;，Linux/macOS 为 :)
    sep = os.pathsep

    # 构建 PyInstaller 命令行参数
    args = [
        'run.py',                                    # 入口脚本
        '--name=AI-API-Hub',                         # 输出文件名
        '--onefile',                                 # 打包为单个文件
        '--noconsole',                               # 不显示控制台窗口（GUI 模式）
        f'--add-data=templates{sep}templates',       # 打包模板目录
        f'--add-data=static{sep}static',             # 打包静态文件目录
        '--hidden-import=flask',                     # 隐式导入 Flask
        '--hidden-import=flask_cors',                # 隐式导入 Flask-CORS
        '--hidden-import=sqlite3',                   # 隐式导入 SQLite3
        '--collect-all=flask',                       # 收集 Flask 全部资源
        '--collect-all=flask_cors',                  # 收集 Flask-CORS 全部资源
    ]

    # 如果图标文件存在，添加图标参数
    if icon_path and os.path.exists(icon_path):
        args.append(f'--icon={icon_path}')

    print("开始打包...")

    # 导入并执行 PyInstaller
    import PyInstaller.__main__                      # 延迟导入，仅在打包时需要
    PyInstaller.__main__.run(args)                   # 执行打包

    # 输出打包结果
    exe_path = os.path.join(dist_dir, 'AI-API-Hub.exe')
    print(f"\n打包完成！可执行文件位置: {exe_path}")


if __name__ == '__main__':
    build()                                          # 执行打包
