"""
字体下载脚本
自动下载所需的中文字体
"""
import os
import urllib.request
import ssl

# 创建SSL上下文，忽略证书验证（某些环境可能需要）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 字体配置
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONTS = {
    "NotoSansCJKsc-Regular.otf": "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    "NotoSansCJKsc-Bold.otf": "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf",
}


def download_font(font_name: str, url: str) -> bool:
    """下载单个字体文件"""
    font_path = os.path.join(FONTS_DIR, font_name)
    
    # 如果字体已存在，跳过下载
    if os.path.exists(font_path):
        print(f"✓ {font_name} 已存在")
        return True
    
    print(f"正在下载 {font_name}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ssl_context, timeout=60) as response:
            with open(font_path, 'wb') as f:
                f.write(response.read())
        print(f"✓ {font_name} 下载完成")
        return True
    except Exception as e:
        print(f"✗ {font_name} 下载失败: {e}")
        # 删除可能不完整的文件
        if os.path.exists(font_path):
            os.remove(font_path)
        return False


def download_all_fonts():
    """下载所有需要的字体"""
    # 创建字体目录
    os.makedirs(FONTS_DIR, exist_ok=True)
    
    print("=" * 50)
    print("开始下载中文字体...")
    print("=" * 50)
    
    success_count = 0
    for font_name, url in FONTS.items():
        if download_font(font_name, url):
            success_count += 1
    
    print("=" * 50)
    print(f"字体下载完成: {success_count}/{len(FONTS)}")
    print("=" * 50)
    
    return success_count == len(FONTS)


if __name__ == "__main__":
    download_all_fonts()
