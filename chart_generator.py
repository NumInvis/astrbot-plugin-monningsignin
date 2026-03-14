"""图表生成模块 - 使用PIL生成股票走势图"""
import io
from PIL import Image, ImageDraw, ImageFont
import os
from typing import List, Dict, Optional



# 字体路径配置 - 优先使用插件目录下的字体
import os
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATHS = [
    os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Bold.otf"),
    os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Regular.otf"),
    "/usr/share/fonts/truetype/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# 字体下载标志
_fonts_checked = False

def _ensure_fonts():
    """确保字体文件存在，如果不存在则尝试下载"""
    global _fonts_checked
    if _fonts_checked:
        return
    _fonts_checked = True
    
    # 检查是否需要下载字体
    regular_font = os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Regular.otf")
    bold_font = os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Bold.otf")
    
    if not os.path.exists(regular_font) or not os.path.exists(bold_font):
        try:
            # 尝试导入并运行下载脚本
            import sys
            sys.path.insert(0, PLUGIN_DIR)
            from download_fonts import download_all_fonts
            download_all_fonts()
        except Exception as e:
            print(f"字体下载失败: {e}")

def get_font(font_size=12):
    """获取字体，优先使用插件自带字体"""
    # 确保字体存在
    _ensure_fonts()
    
    for font_path in FONT_PATHS:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, font_size)
            except:
                continue
    return ImageFont.load_default()


def generate_stock_chart(
    stock_name: str, 
    price_data: List[Dict], 
    user_holdings: Optional[Dict] = None,
    width: int = 800, 
    height: int = 500
) -> bytes:
    """
    生成股票走势图
    
    Args:
        stock_name: 股票名称
        price_data: 价格数据列表，每个元素包含 'timestamp' 和 'price'
        user_holdings: 玩家持仓信息，包含 'avg_price', 'buy_points', 'sell_points'
        width: 图片宽度
        height: 图片高度
    
    Returns:
        图片字节数据
    """
    if not price_data:
        return generate_empty_chart(stock_name, width, height)
    
    # 创建图片
    img = Image.new('RGB', (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    
    # 边距 - 增加顶部边距避免文字重叠
    margin_left = 80
    margin_right = 40
    margin_top = 100  # 增加顶部边距
    margin_bottom = 60
    
    # 绘图区域
    chart_width = width - margin_left - margin_right
    chart_height = height - margin_top - margin_bottom
    
    # 获取价格范围
    prices = [d['price'] for d in price_data]
    min_price = min(prices)
    max_price = max(prices)
    
    # 如果有持仓信息，考虑持仓价格范围
    if user_holdings and user_holdings.get('avg_price'):
        avg_price = user_holdings['avg_price']
        min_price = min(min_price, avg_price * 0.9)
        max_price = max(max_price, avg_price * 1.1)
    
    price_range = max_price - min_price if max_price != min_price else 1
    
    # 添加边距到价格范围
    price_padding = price_range * 0.1
    min_price -= price_padding
    max_price += price_padding
    price_range = max_price - min_price
    
    # 加载字体 - 优先使用插件自带的中文字体
    try:
        title_font = ImageFont.truetype(os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Bold.otf"), 24)
        price_font = ImageFont.truetype(os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Regular.otf"), 16)
        label_font = ImageFont.truetype(os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Regular.otf"), 12)
        small_font = ImageFont.truetype(os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Regular.otf"), 10)
    except:
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            price_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
            label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except:
            title_font = ImageFont.load_default()
            price_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
    
    # 标题 - 不带表情符号
    title = f"{stock_name} 价格走势"
    draw.text((margin_left, 15), title, fill=(255, 255, 255), font=title_font)
    
    # 当前价格
    current_price = prices[-1]
    current_price_text = f"当前价格: {current_price:.2f}"
    draw.text((margin_left, 50), current_price_text, fill=(200, 200, 200), font=price_font)
    
    # 如果有持仓信息，显示在右上角
    if user_holdings:
        avg_price = user_holdings.get('avg_price', 0)
        total_qty = user_holdings.get('total_quantity', 0)
        if avg_price > 0 and total_qty > 0:
            profit = (current_price - avg_price) * total_qty
            profit_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
            
            # 根据盈亏选择颜色
            if profit >= 0:
                profit_color = (0, 255, 100)  # 绿色
            else:
                profit_color = (255, 80, 80)  # 红色
            
            # 持仓信息 - 显示在右上角
            holding_text = f"持仓: {total_qty}股 | 均价: {avg_price:.2f}"
            profit_text = f"盈亏: {profit:+.2f} ({profit_pct:+.2f}%)"
            
            # 计算文本宽度右对齐
            holding_bbox = draw.textbbox((0, 0), holding_text, font=price_font)
            profit_bbox = draw.textbbox((0, 0), profit_text, font=price_font)
            
            holding_x = width - margin_right - (holding_bbox[2] - holding_bbox[0])
            profit_x = width - margin_right - (profit_bbox[2] - profit_bbox[0])
            
            draw.text((holding_x, 15), holding_text, fill=(200, 200, 200), font=price_font)
            draw.text((profit_x, 35), profit_text, fill=profit_color, font=price_font)
    
    # 根据涨跌选择线条颜色
    start_price = prices[0]
    if current_price >= start_price:
        line_color = (0, 255, 100)  # 绿色（涨）
    else:
        line_color = (255, 80, 80)  # 红色（跌）
    
    # 绘制网格线
    grid_color = (60, 60, 60)
    for i in range(6):
        y = margin_top + (chart_height * i // 5)
        draw.line([(margin_left, y), (margin_left + chart_width, y)], fill=grid_color, width=1)
    
    # 绘制Y轴价格标签
    for i in range(6):
        price_val = max_price - (price_range * i / 5)
        y = margin_top + (chart_height * i // 5)
        price_text = f"{price_val:.1f}"
        draw.text((10, y - 8), price_text, fill=(150, 150, 150), font=label_font)
    
    # 计算所有点的坐标
    points = []
    for i, data in enumerate(price_data):
        x = margin_left + (chart_width * i // (len(price_data) - 1)) if len(price_data) > 1 else margin_left + chart_width // 2
        y = margin_top + chart_height - ((data['price'] - min_price) / price_range * chart_height)
        # 兼容 'timestamp' 和 'time' 两种键名
        timestamp = data.get('timestamp') or data.get('time', '')
        points.append((x, int(y), data['price'], timestamp))
    
    # 绘制价格走势线
    if len(points) > 1:
        line_points = [(p[0], p[1]) for p in points]
        draw.line(line_points, fill=line_color, width=2)
    
    # 绘制玩家持仓标记
    if user_holdings:
        avg_price = user_holdings.get('avg_price', 0)
        buy_points = user_holdings.get('buy_points', [])
        sell_points = user_holdings.get('sell_points', [])
        
        # 绘制均价线（虚线）
        if avg_price > 0:
            avg_y = margin_top + chart_height - ((avg_price - min_price) / price_range * chart_height)
            # 绘制虚线
            for x in range(margin_left, margin_left + chart_width, 10):
                draw.line([(x, int(avg_y)), (x + 5, int(avg_y))], fill=(255, 255, 0), width=1)
            # 标注
            draw.text((margin_left + 5, int(avg_y) - 15), f"均价: {avg_price:.2f}", 
                     fill=(255, 255, 0), font=small_font)
        
        # 绘制买入点（绿色圆圈）
        for buy_price in buy_points:
            if min_price <= buy_price <= max_price:
                # 找到最接近的时间点
                closest_point = min(points, key=lambda p: abs(p[2] - buy_price))
                x, y = closest_point[0], closest_point[1]
                draw.ellipse([(x-6, y-6), (x+6, y+6)], outline=(0, 255, 0), width=2)
                draw.text((x-10, y-20), "B", fill=(0, 255, 0), font=small_font)
        
        # 绘制卖出点（红色叉）
        for sell_price in sell_points:
            if min_price <= sell_price <= max_price:
                closest_point = min(points, key=lambda p: abs(p[2] - sell_price))
                x, y = closest_point[0], closest_point[1]
                # 绘制红色叉
                draw.line([(x-5, y-5), (x+5, y+5)], fill=(255, 0, 0), width=2)
                draw.line([(x-5, y+5), (x+5, y-5)], fill=(255, 0, 0), width=2)
                draw.text((x-10, y-20), "S", fill=(255, 0, 0), font=small_font)
    
    # 绘制X轴时间标签（只显示首尾）
    if len(price_data) > 0:
        # 兼容 'timestamp' 和 'time' 两种键名
        first_ts = price_data[0].get('timestamp') or price_data[0].get('time', '')
        last_ts = price_data[-1].get('timestamp') or price_data[-1].get('time', '')
        first_time = first_ts.split()[1] if ' ' in first_ts else first_ts[-5:] if len(first_ts) >= 5 else first_ts
        last_time = last_ts.split()[1] if ' ' in last_ts else last_ts[-5:] if len(last_ts) >= 5 else last_ts
        
        draw.text((margin_left, height - 40), first_time, fill=(150, 150, 150), font=label_font)
        draw.text((width - margin_right - 50, height - 40), last_time, fill=(150, 150, 150), font=label_font)
    
    # 绘制边框
    draw.rectangle([(margin_left, margin_top), (margin_left + chart_width, margin_top + chart_height)], 
                   outline=(100, 100, 100), width=2)
    
    # 保存为字节
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG', optimize=True)
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()


def generate_empty_chart(stock_name: str, width: int = 800, height: int = 500) -> bytes:
    """生成空数据提示图"""
    img = Image.new('RGB', (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(os.path.join(PLUGIN_DIR, "fonts", "NotoSansCJKsc-Bold.otf"), 32)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
        except:
            font = ImageFont.load_default()

    # 不带表情符号
    text = f"{stock_name}\n暂无价格数据"
    draw.text((width // 2 - 150, height // 2 - 40), text, fill=(200, 200, 200), font=font)

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG', optimize=True)
    img_byte_arr.seek(0)
    return img_byte_arr.getvalue()
