# -*- coding: utf-8 -*-
# AI API Hub — 应用图标生成器
# 使用 Pillow 库程序化生成 .ico 图标文件

from PIL import Image, ImageDraw  # 图像处理库：Image 用于创建图像，ImageDraw 用于绑制图形
import os                         # 操作系统接口，用于路径处理


def create_icon():
    """生成应用图标（多尺寸 ICO 格式）"""

    # 定义图标尺寸列表：16x16（任务栏）、32x32（桌面）、48x48（标题栏）、256x256（高清）
    sizes = [16, 32, 48, 256]

    # 创建各尺寸的图像
    images = []
    for size in sizes:
        # 创建 RGBA 模式图像（支持透明度），背景透明
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)                       # 创建绘图对象

        # 计算缩放比例（基于 256 像素的设计稿）
        scale = size / 256

        # 绘制圆角矩形背景（Indigo 主色调）
        bg_radius = int(40 * scale)                      # 圆角半径
        draw.rounded_rectangle(
            [0, 0, size - 1, size - 1],                  # 矩形范围
            radius=bg_radius,                            # 圆角半径
            fill=(99, 102, 241, 255)                     # Indigo 色 (#6366F1)
        )

        # 绘制四个白色小方块（2x2 网格，代表 API 卡片）
        # 左上角方块
        draw.rounded_rectangle(
            [int(40 * scale), int(60 * scale), int(128 * scale), int(120 * scale)],
            radius=int(12 * scale),
            fill=(255, 255, 255, 255)                    # 纯白色
        )
        # 右上角方块（80% 不透明度）
        draw.rounded_rectangle(
            [int(128 * scale), int(60 * scale), int(216 * scale), int(120 * scale)],
            radius=int(12 * scale),
            fill=(255, 255, 255, 204)                    # 白色 80% 不透明
        )
        # 左下角方块（80% 不透明度）
        draw.rounded_rectangle(
            [int(40 * scale), int(130 * scale), int(128 * scale), int(190 * scale)],
            radius=int(12 * scale),
            fill=(255, 255, 255, 204)                    # 白色 80% 不透明
        )
        # 右下角方块
        draw.rounded_rectangle(
            [int(128 * scale), int(130 * scale), int(216 * scale), int(190 * scale)],
            radius=int(12 * scale),
            fill=(255, 255, 255, 255)                    # 纯白色
        )

        # 顶部绿色圆点（状态指示器/装饰元素）
        draw.ellipse(
            [int(108 * scale), int(30 * scale), int(148 * scale), int(70 * scale)],
            fill=(34, 197, 94, 255)                      # 绿色 (#22C55E)
        )

        images.append(img)                               # 将图像添加到列表

    # 保存为 ICO 格式（包含多尺寸）
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
    images[-1].save(                                     # 使用最大尺寸图像作为主图像
        icon_path,
        format='ICO',
        sizes=[(s, s) for s in sizes],                   # 指定所有尺寸
        append_images=images[:-1]                        # 附加其他尺寸
    )
    print(f"图标已生成: {icon_path}")                     # 输出成功信息


if __name__ == '__main__':
    try:
        create_icon()                                    # 执行图标生成
    except ImportError:
        # Pillow 未安装时的友好提示
        print("需要安装 Pillow 库才能生成图标")
        print("请运行: pip install Pillow")
    except Exception as e:
        # 其他错误的处理
        print(f"图标生成失败: {e}")
