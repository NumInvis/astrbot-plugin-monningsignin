"""股票服务模块"""
import os
import sys
# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiosqlite
import random
import asyncio
from datetime import datetime, timedelta
from config import CONFIG


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_num(n: int) -> str:
    return f"{n:,}"


def mask_id(uid: str) -> str:
    if len(uid) <= 4:
        return uid
    return uid[:3] + "***" + uid[-2:]


class StockService:
    """股票服务类"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        # 每个股票独立的市场情绪
        self.stock_sentiments = {}  # {stock_name: sentiment}
        self.last_sentiment_update = datetime.now()
        self.sentiment_update_interval = random.randint(3600, 43200)  # 1h-12h
        self.last_market_update = datetime.now()
        self.market_update_interval = 600  # 10分钟
        # 启动市场更新任务
        asyncio.create_task(self._market_update_task())
        asyncio.create_task(self._sentiment_update_task())

    async def _market_update_task(self):
        """市场更新任务"""
        while True:
            await asyncio.sleep(self.market_update_interval)
            await self._update_market_prices()

    async def _sentiment_update_task(self):
        """市场情绪更新任务"""
        while True:
            await asyncio.sleep(self.sentiment_update_interval)
            await self._update_stock_sentiments()
            # 随机下次更新时间
            self.sentiment_update_interval = random.randint(3600, 43200)

    async def _update_market_prices(self):
        """更新市场价格"""
        async with aiosqlite.connect(self.db_path) as db:
            # 确保历史价格表存在
            await db.execute("""
                CREATE TABLE IF NOT EXISTS stock_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_name TEXT,
                    price REAL,
                    timestamp TEXT,
                    FOREIGN KEY (stock_name) REFERENCES stock_prices(stock_name)
                )
            """)

            cursor = await db.execute(
                "SELECT stock_name, current_price FROM stock_prices WHERE delisted = 0"
            )
            stocks = await cursor.fetchall()

            for stock_name, current_price in stocks:
                # 获取该股票的独立市场情绪（默认为中立）
                sentiment = self.stock_sentiments.get(stock_name, "中立")

                # 根据市场情绪调整波动幅度（已削弱影响）
                if sentiment == "恐慌":
                    change = random.uniform(-0.03, -0.005)  # 原来是 -0.05 ~ -0.01
                elif sentiment == "悲观":
                    change = random.uniform(-0.02, 0.005)   # 原来是 -0.03 ~ 0.01
                elif sentiment == "中立":
                    change = random.uniform(-0.015, 0.015)  # 原来是 -0.02 ~ 0.02
                elif sentiment == "乐观":
                    change = random.uniform(-0.005, 0.02)   # 原来是 -0.01 ~ 0.03
                elif sentiment == "贪婪":
                    change = random.uniform(0.005, 0.03)    # 原来是 0.01 ~ 0.05

                new_price = current_price * (1 + change)

                # 更新当前价格
                await db.execute(
                    "UPDATE stock_prices SET current_price = ?, last_update = ? WHERE stock_name = ?",
                    (new_price, now_str(), stock_name)
                )

                # 保存历史价格
                await db.execute(
                    "INSERT INTO stock_price_history (stock_name, price, timestamp) VALUES (?, ?, ?)",
                    (stock_name, new_price, now_str())
                )

            await db.commit()

    async def _update_stock_sentiments(self):
        """更新每个股票的独立市场情绪"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT stock_name FROM stock_prices WHERE delisted = 0"
            )
            stocks = await cursor.fetchall()

            sentiments = ["恐慌", "悲观", "中立", "乐观", "贪婪"]
            for (stock_name,) in stocks:
                # 每个股票独立随机选择情绪
                self.stock_sentiments[stock_name] = random.choice(sentiments)

        self.last_sentiment_update = datetime.now()

    async def get_stock_sentiment(self, stock_name: str) -> str:
        """获取指定股票的市场情绪"""
        # 检查是否需要更新
        if (datetime.now() - self.last_sentiment_update).total_seconds() > self.sentiment_update_interval:
            await self._update_stock_sentiments()
        return self.stock_sentiments.get(stock_name, "中立")

    async def get_all_sentiments(self) -> dict:
        """获取所有股票的市场情绪"""
        # 检查是否需要更新
        if (datetime.now() - self.last_sentiment_update).total_seconds() > self.sentiment_update_interval:
            await self._update_stock_sentiments()
        return self.stock_sentiments.copy()
    
    async def get_stock_market(self) -> list:
        """获取股市行情"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT stock_name, current_price, base_price, emoji, desc, owner_id
                   FROM stock_prices WHERE delisted = 0 ORDER BY current_price DESC""",
            )
            stocks = await cursor.fetchall()
            
            # 获取昵称映射
            cursor = await db.execute("SELECT user_id, nickname FROM user_info WHERE nickname IS NOT NULL")
            name_map = {str(row[0]): row[1] for row in await cursor.fetchall()}
        
        stock_list = []
        for stock in stocks:
            name, price, base, emoji, desc, owner_id = stock
            change_pct = ((price - base) / base * 100) if base > 0 else 0
            arrow = "📈" if change_pct >= 0 else "📉"
            
            owner_str = ""
            if owner_id:
                owner_name = name_map.get(str(owner_id), mask_id(str(owner_id)))
                owner_str = f"\n   👑 拥有者：{owner_name}"
            
            market_cap = int(price * 1000000)  # 100万股
            
            stock_list.append({
                "name": name,
                "price": price,
                "base": base,
                "emoji": emoji or "🏭",
                "desc": desc or "玩家企业",
                "owner_id": owner_id,
                "owner_str": owner_str,
                "change_pct": change_pct,
                "arrow": arrow,
                "market_cap": market_cap
            })
        
        return stock_list
    
    async def buy_stock(self, user_id: str, stock_name: str, quantity: float) -> dict:
        """买入股票"""
        if quantity <= 0:
            return {"success": False, "message": "数量必须大于0"}
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT current_price FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "股票不存在或已退市"}
            
            price = row[0]
            
            # 大额交易影响价格
            if quantity > 10000:
                # 每10000股价格上涨0.5%
                price_increase = min(0.1, quantity / 10000 * 0.005)
                price = price * (1 + price_increase)
                # 更新股票价格
                await db.execute(
                    "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                    (price, stock_name)
                )
            
            total_cost = int(price * quantity)
            
            # 检查余额
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "message": "用户不存在"}
            
            try:
                balance = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                balance = 0
            
            if balance < total_cost:
                return {"success": False, "message": f"余额不足！需要{format_num(total_cost)}星声"}
            
            now = now_str()
            
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (total_cost, user_id)
            )
            await db.execute(
                """INSERT INTO stock_holdings 
                    (user_id, stock_name, quantity, buy_price, buy_time, remaining, last_dividend_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, stock_name, quantity, price, now, quantity, today_str())
            )
            
            # 检查是否成为控股股东
            await self._check_controlling_shareholder(db, user_id, stock_name)
            
            await db.commit()
        
        return {
            "success": True,
            "stock_name": stock_name,
            "price": price,
            "quantity": quantity,
            "total_cost": total_cost
        }
    
    async def sell_stock(self, user_id: str, stock_name: str, want_sell: float) -> dict:
        """卖出股票"""
        if want_sell <= 0:
            return {"success": False, "message": "数量必须大于0"}
        
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT current_price FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "股票不存在或已退市"}
            
            price = row[0]
            
            # 大额交易影响价格
            if want_sell > 10000:
                # 每10000股价格下跌0.5%
                price_decrease = min(0.1, want_sell / 10000 * 0.005)
                price = price * (1 - price_decrease)
                # 更新股票价格
                await db.execute(
                    "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                    (price, stock_name)
                )
            
            # 获取可卖持仓
            cursor = await db.execute(
                """SELECT id, remaining, buy_price FROM stock_holdings
                   WHERE user_id = ? AND stock_name = ? AND remaining > 0
                   ORDER BY buy_time ASC""",
                (user_id, stock_name)
            )
            holdings = await cursor.fetchall()
            
            if not holdings:
                return {"success": False, "message": "你没有该股票持仓"}
            
            total_available = sum(h[1] for h in holdings)
            if total_available < want_sell:
                return {"success": False, "message": f"可卖数量不足！可卖：{total_available}股"}
            
            # 计算卖出金额
            sell_amount = int(price * want_sell)
            fee = max(1, int(sell_amount * 0.001))
            net_amount = sell_amount - fee
            
            # 扣减持仓
            remaining_to_sell = want_sell
            for holding_id, hold_qty, buy_price in holdings:
                if remaining_to_sell <= 0:
                    break
                sell_from_this = min(remaining_to_sell, hold_qty)
                new_remaining = hold_qty - sell_from_this
                await db.execute(
                    "UPDATE stock_holdings SET remaining = ? WHERE id = ?",
                    (new_remaining, holding_id)
                )
                remaining_to_sell -= sell_from_this
            
            # 加钱
            await db.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (net_amount, user_id)
            )
            
            # 检查是否失去控股股东地位
            await self._check_controlling_shareholder(db, user_id, stock_name)
            
            await db.commit()
        
        return {
            "success": True,
            "stock_name": stock_name,
            "price": price,
            "quantity": want_sell,
            "sell_amount": sell_amount,
            "fee": fee,
            "net_amount": net_amount
        }
    
    async def get_portfolio(self, user_id: str) -> dict:
        """查看持仓"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """SELECT stock_name, SUM(remaining) as total_qty,
                       SUM(remaining * buy_price) / SUM(remaining) as avg_cost
                   FROM stock_holdings 
                   WHERE user_id = ? AND remaining > 0 
                   GROUP BY stock_name""",
                (user_id,)
            )
            holdings = await cursor.fetchall()
        
        if not holdings:
            return {"success": False, "message": "你还没有股票持仓\n发送 /股市 查看行情"}
        
        portfolio = []
        total_value = 0
        total_cost = 0
        
        async with aiosqlite.connect(self.db_path) as db:
            for stock_name, qty, avg_cost in holdings:
                if not qty or qty <= 0:
                    continue
                
                cursor = await db.execute(
                    "SELECT current_price, emoji FROM stock_prices WHERE stock_name = ?",
                    (stock_name,)
                )
                stock_row = await cursor.fetchone()
                
                if not stock_row:
                    continue
                
                current_price = stock_row[0]
                emoji = stock_row[1] or "🏭"
                
                market_value = int(qty * current_price)
                cost_basis = int(qty * avg_cost)
                profit = market_value - cost_basis
                profit_pct = (profit / cost_basis * 100) if cost_basis > 0 else 0
                
                total_value += market_value
                total_cost += cost_basis
                
                arrow = "📈" if profit >= 0 else "📉"
                
                portfolio.append({
                    "stock_name": stock_name,
                    "emoji": emoji,
                    "quantity": qty,
                    "avg_cost": avg_cost,
                    "current_price": current_price,
                    "market_value": market_value,
                    "cost_basis": cost_basis,
                    "profit": profit,
                    "profit_pct": profit_pct,
                    "arrow": arrow
                })
        
        total_profit = total_value - total_cost
        total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "success": True,
            "portfolio": portfolio,
            "total_value": total_value,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct
        }
    
    async def create_company(self, user_id: str, company_name: str, init_price: float, desc: str) -> dict:
        """创立上市公司"""
        if init_price < 1 or init_price > 10000:
            return {"success": False, "message": "初始股价需在1-10000之间"}
        
        # 检查资金
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "message": "用户不存在"}
            
            try:
                balance = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                balance = 0
            
            required = int(CONFIG.STOCK_MIN_CAPITAL)
            if balance < required:
                return {"success": False, "message": f"资金不足！创立公司需要{format_num(required)}星声"}
            
            # 检查公司名是否已存在
            cursor = await db.execute(
                "SELECT 1 FROM stock_prices WHERE stock_name = ?",
                (company_name,)
            )
            if await cursor.fetchone():
                return {"success": False, "message": "该公司名已被使用"}
            
            # 创建公司
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (required, user_id)
            )
            await db.execute(
                """INSERT INTO stock_prices 
                    (stock_name, current_price, base_price, owner_id, emoji, desc, last_update)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (company_name, init_price, init_price, user_id, "🏢", desc, today_str())
            )
            
            # 创始人获得初始股份
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 应用金色成就加成：创立公司时额外赠送股份
            cursor = await db.execute(
                "SELECT SUM(bonus_value) FROM achievement_bonuses WHERE user_id = ? AND bonus_type = 'company_shares_bonus'",
                (user_id,)
            )
            bonus_result = await cursor.fetchone()
            shares_bonus = int(bonus_result[0]) if bonus_result and bonus_result[0] else 0
            
            base_shares = 100000
            total_shares = base_shares + shares_bonus
            
            await db.execute(
                """INSERT INTO stock_holdings 
                    (user_id, stock_name, quantity, buy_price, buy_time, remaining, last_dividend_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, company_name, total_shares, init_price, now, total_shares, today_str())
            )
            await db.commit()
        
        return {
            "success": True,
            "company_name": company_name,
            "init_price": init_price,
            "desc": desc,
            "required": required
        }
    
    async def bankrupt(self, user_id: str, company_name: str) -> dict:
        """宣告公司破产"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT owner_id FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (company_name,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "公司不存在或已退市"}
            
            if str(row[0]) != user_id:
                return {"success": False, "message": "只有公司创始人可以宣告破产"}
            
            # 退市
            await db.execute(
                "UPDATE stock_prices SET delisted = 1 WHERE stock_name = ?",
                (company_name,)
            )
            await db.commit()
        
        return {
            "success": True,
            "company_name": company_name
        }
    
    async def research(self, user_id: str, company_name: str, amount: int) -> dict:
        """公司研发（提升股价）"""
        if amount < 10000:
            return {"success": False, "message": "研发资金至少10000星声"}
        
        # 检查余额
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            if not row:
                return {"success": False, "message": "用户不存在"}
            
            try:
                balance = int(row[0]) if row[0] else 0
            except (ValueError, TypeError):
                balance = 0
            
            if balance < amount:
                return {"success": False, "message": f"余额不足！当前：{format_num(balance)}星声"}
            
            # 检查公司
            cursor = await db.execute(
                "SELECT owner_id, current_price FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (company_name,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "公司不存在或已退市"}
            
            # 研发效果：每投入10万，股价+1%
            boost = amount / 100000 * 0.01
            new_price = row[1] * (1 + boost)
            
            await db.execute(
                "UPDATE users SET balance = balance - ? WHERE user_id = ?",
                (amount, user_id)
            )
            await db.execute(
                "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                (new_price, company_name)
            )
            await db.commit()
        
        return {
            "success": True,
            "company_name": company_name,
            "amount": amount,
            "boost": boost,
            "new_price": new_price
        }
    
    async def _check_controlling_shareholder(self, db, user_id: str, stock_name: str):
        """检查控股股东"""
        # 计算总股数
        cursor = await db.execute(
            "SELECT SUM(remaining) FROM stock_holdings WHERE stock_name = ?",
            (stock_name,)
        )
        total_shares = await cursor.fetchone()
        total_shares = total_shares[0] if total_shares and total_shares[0] else 1
        
        # 计算用户持股数
        cursor = await db.execute(
            "SELECT SUM(remaining) FROM stock_holdings WHERE user_id = ? AND stock_name = ?",
            (user_id, stock_name)
        )
        user_shares = await cursor.fetchone()
        user_shares = user_shares[0] if user_shares and user_shares[0] else 0
        
        # 计算持股比例
        share_ratio = user_shares / total_shares
        
        # 如果持股超过50%，成为控股股东
        if share_ratio > 0.5:
            await db.execute(
                "UPDATE stock_prices SET owner_id = ? WHERE stock_name = ?",
                (user_id, stock_name)
            )
        else:
            # 检查是否还有其他控股股东
            cursor = await db.execute(
                """SELECT user_id, SUM(remaining) as shares
                   FROM stock_holdings 
                   WHERE stock_name = ? 
                   GROUP BY user_id 
                   HAVING shares > ?
                   ORDER BY shares DESC
                   LIMIT 1""",
                (stock_name, total_shares * 0.5)
            )
            new_owner = await cursor.fetchone()
            if new_owner:
                await db.execute(
                    "UPDATE stock_prices SET owner_id = ? WHERE stock_name = ?",
                    (new_owner[0], stock_name)
                )
            else:
                await db.execute(
                    "UPDATE stock_prices SET owner_id = NULL WHERE stock_name = ?",
                    (stock_name,)
                )
    
    async def get_shareholders(self, stock_name: str) -> dict:
        """获取股东列表"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查股票是否存在
            cursor = await db.execute(
                "SELECT 1 FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            if not await cursor.fetchone():
                return {"success": False, "message": "股票不存在或已退市"}
            
            # 获取总股数
            cursor = await db.execute(
                "SELECT SUM(remaining) FROM stock_holdings WHERE stock_name = ?",
                (stock_name,)
            )
            total_shares = await cursor.fetchone()
            total_shares = total_shares[0] if total_shares and total_shares[0] else 1
            
            # 获取股东列表
            cursor = await db.execute(
                """SELECT user_id, SUM(remaining) as shares
                   FROM stock_holdings 
                   WHERE stock_name = ? AND remaining > 0
                   GROUP BY user_id 
                   ORDER BY shares DESC""",
                (stock_name,)
            )
            shareholders = await cursor.fetchall()
            
            # 获取昵称映射
            user_ids = [s[0] for s in shareholders]
            name_map = {}
            if user_ids:
                placeholders = ','.join(['?'] * len(user_ids))
                cursor = await db.execute(
                    f"SELECT user_id, nickname FROM user_info WHERE user_id IN ({placeholders})",
                    user_ids
                )
                for row in await cursor.fetchall():
                    name_map[str(row[0])] = row[1]
            
            # 构建股东信息
            shareholder_list = []
            for user_id, shares in shareholders:
                ratio = shares / total_shares * 100
                name = name_map.get(str(user_id), mask_id(str(user_id)))
                shareholder_list.append({
                    "user_id": user_id,
                    "name": name,
                    "shares": shares,
                    "ratio": ratio
                })
            
            # 获取控股股东
            cursor = await db.execute(
                "SELECT owner_id FROM stock_prices WHERE stock_name = ?",
                (stock_name,)
            )
            owner_id = await cursor.fetchone()
            owner_id = owner_id[0] if owner_id else None
            
            owner_info = None
            if owner_id:
                owner_name = name_map.get(str(owner_id), mask_id(str(owner_id)))
                owner_info = {
                    "user_id": owner_id,
                    "name": owner_name
                }
        
        return {
            "success": True,
            "stock_name": stock_name,
            "total_shares": total_shares,
            "shareholders": shareholder_list,
            "controlling_shareholder": owner_info
        }
    
    async def pay_dividend(self, stock_name: str) -> dict:
        """发放股息"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查股票是否存在
            cursor = await db.execute(
                "SELECT current_price, owner_id FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            stock_info = await cursor.fetchone()
            if not stock_info:
                return {"success": False, "message": "股票不存在或已退市"}
            
            current_price, owner_id = stock_info
            
            # 计算股息金额（基础2%）
            dividend_rate = 0.02
            
            # 获取弗糯结社人数，增加额外股息
            cursor = await db.execute(
                "SELECT COUNT(*) FROM user_society WHERE society_name = '弗糯结社'"
            )
            nuo_count = await cursor.fetchone()
            nuo_count = nuo_count[0] if nuo_count else 0
            extra_rate = nuo_count * 0.001
            dividend_rate += extra_rate
            
            # 获取股东列表
            cursor = await db.execute(
                """SELECT user_id, SUM(remaining) as shares
                   FROM stock_holdings 
                   WHERE stock_name = ? AND remaining > 0
                   GROUP BY user_id""",
                (stock_name,)
            )
            shareholders = await cursor.fetchall()
            
            if not shareholders:
                return {"success": False, "message": "没有股东"}
            
            # 发放股息
            total_dividend = 0
            for user_id, shares in shareholders:
                dividend = int(shares * current_price * dividend_rate)
                if dividend > 0:
                    await db.execute(
                        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                        (dividend, user_id)
                    )
                    total_dividend += dividend
            
            await db.commit()
        
        return {
            "success": True,
            "stock_name": stock_name,
            "dividend_rate": dividend_rate * 100,
            "total_dividend": total_dividend
        }
    
    async def trigger_market_event(self) -> dict:
        """触发市场事件"""
        events = [
            {"type": "行业利好", "effect": "相关行业股票上涨", "probability": 0.3},
            {"type": "行业利空", "effect": "相关行业股票下跌", "probability": 0.3},
            {"type": "公司并购", "effect": "目标公司股票上涨", "probability": 0.1},
            {"type": "政策利好", "effect": "整体市场上涨", "probability": 0.15},
            {"type": "政策利空", "effect": "整体市场下跌", "probability": 0.15}
        ]
        
        # 随机选择事件
        event = random.choices(events, weights=[e["probability"] for e in events], k=1)[0]
        
        # 执行事件影响
        async with aiosqlite.connect(self.db_path) as db:
            if event["type"] in ["政策利好", "政策利空"]:
                # 影响整体市场
                cursor = await db.execute(
                    "SELECT stock_name, current_price FROM stock_prices WHERE delisted = 0"
                )
                stocks = await cursor.fetchall()
                
                for stock_name, current_price in stocks:
                    if event["type"] == "政策利好":
                        change = random.uniform(0.02, 0.05)
                    else:
                        change = random.uniform(-0.05, -0.02)
                    
                    new_price = current_price * (1 + change)
                    await db.execute(
                        "UPDATE stock_prices SET current_price = ? WHERE stock_name = ?",
                        (new_price, stock_name)
                    )
            
            await db.commit()
        
        return {
            "success": True,
            "event_type": event["type"],
            "effect": event["effect"]
        }
    
    async def get_stock_kline(self, stock_name: str) -> dict:
        """获取股票最近24小时每10分钟的价格"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查股票是否存在
            cursor = await db.execute(
                "SELECT current_price FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            row = await cursor.fetchone()

            if not row:
                return {"success": False, "message": "股票不存在或已退市"}

            current_price = row[0]

            # 获取最近24小时的历史价格数据
            cutoff_time = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute(
                """
                SELECT price, timestamp
                FROM stock_price_history
                WHERE stock_name = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (stock_name, cutoff_time)
            )
            history = await cursor.fetchall()

        # 处理历史数据，按每10分钟分组，取平均价格
        price_data = []
        if history:
            # 按每10分钟分组处理数据
            ten_min_data = {}
            for price, timestamp_str in history:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                # 计算10分钟区间
                minute_block = (timestamp.minute // 10) * 10
                time_key = timestamp.strftime(f"%Y-%m-%d %H:{minute_block:02d}")

                if time_key not in ten_min_data:
                    ten_min_data[time_key] = []
                ten_min_data[time_key].append(price)

            # 生成每10分钟的平均价格
            for time_key, prices in sorted(ten_min_data.items()):
                if prices:
                    avg_price = sum(prices) / len(prices)
                    price_data.append({
                        "timestamp": time_key,
                        "price": round(avg_price, 2)
                    })

        return {
            "success": True,
            "stock_name": stock_name,
            "price_data": price_data
        }
    
    async def get_price_history(self, stock_name: str) -> dict:
        """获取股票最近24小时的价格历史（每10分钟一个点）"""
        async with aiosqlite.connect(self.db_path) as db:
            # 检查股票是否存在
            cursor = await db.execute(
                "SELECT current_price FROM stock_prices WHERE stock_name = ? AND delisted = 0",
                (stock_name,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return {"success": False, "message": "股票不存在或已退市"}
            
            current_price = row[0]
            
            # 获取最近24小时的历史价格数据
            cutoff_time = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
            cursor = await db.execute(
                """
                SELECT price, timestamp 
                FROM stock_price_history 
                WHERE stock_name = ? AND timestamp >= ? 
                ORDER BY timestamp ASC
                """,
                (stock_name, cutoff_time)
            )
            history = await cursor.fetchall()
        
        # 处理历史数据，生成每10分钟的价格点
        price_data = []
        
        if history:
            # 将数据按10分钟分组
            for price, timestamp_str in history:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                time_key = timestamp.strftime("%m-%d %H:%M")
                
                price_data.append({
                    "time": time_key,
                    "price": float(price)
                })
        
        # 如果没有历史数据或数据不足，生成模拟数据
        if len(price_data) < 10:
            # 基于当前价格生成最近24小时的模拟数据（每10分钟一个点）
            now = datetime.now()
            base_price = current_price
            
            for i in range(144, -1, -6):  # 24小时 = 144个10分钟，每小时显示一个点
                time_point = now - timedelta(minutes=i*10)
                time_key = time_point.strftime("%m-%d %H:%M")
                
                # 生成略微波动的价格
                import random
                variation = random.uniform(-0.02, 0.02)  # ±2%波动
                sim_price = base_price * (1 + variation)
                
                price_data.append({
                    "time": time_key,
                    "price": round(sim_price, 2)
                })
            
            # 按时间排序
            price_data.sort(key=lambda x: x["time"])
        
        return {
            "success": True,
            "stock_name": stock_name,
            "price_data": price_data
        }
