# 重复造轮子代码审查报告

## 审查日期
2026-04-02

---

## 1. 重复方法清单

### 1.1 获取用户资产方法（高度重复）

#### 问题描述
`_get_user_asset()` 方法在多个service中重复实现，代码相似度超过90%。

#### 重复位置

| 文件 | 行号 | 代码行数 | 用途 |
|------|------|---------|------|
| `society_service.py` | 276-310 | 35行 | 结社资产排名计算 |
| `stock_service.py` | 800-830 | 31行 | 股票交易资产验证 |
| `work_service.py` | 114-167 | 54行 | 工资计算资产参考 |
| `tarot_service.py` | 246-269 | 24行 | 塔罗牌效果资产计算 |
| `tax_service.py` | 293-323 | 31行 | 税收计算资产统计 |

#### 代码对比

**society_service.py 版本：**
```python
async def _get_user_asset(self, user_id: str) -> tuple:
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            "SELECT balance, bank_balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return (0, 0, 0, 0)
        
        try:
            cash = int(row[0]) if row[0] else 0
        except (ValueError, TypeError):
            cash = 0
        try:
            bank = int(row[1]) if row[1] else 0
        except (ValueError, TypeError):
            bank = 0
        
        # 计算股票市值
        cursor = await db.execute(
            """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
               FROM stock_holdings sh
               JOIN stock_prices sp ON sh.stock_name = sp.stock_name
               WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
            (user_id,)
        )
        stock_row = await cursor.fetchone()
        stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
    
    return cash + bank + stock, cash, bank, stock
```

**stock_service.py 版本：**
```python
async def _get_user_asset(self, user_id: str) -> tuple:
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            "SELECT balance, bank_balance FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        
        if not row:
            return (0, 0, 0, 0)
        
        cash = int(row[0]) if row[0] else 0
        bank = int(row[1]) if row[1] else 0
        
        # 计算股票市值
        cursor = await db.execute(
            """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
               FROM stock_holdings sh
               JOIN stock_prices sp ON sh.stock_name = sp.stock_name
               WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
            (user_id,)
        )
        stock_row = await cursor.fetchone()
        stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
    
    return cash + bank + stock, cash, bank, stock
```

#### 差异分析
- society_service.py 有额外的 try-except 错误处理
- 其他版本基本相同
- 返回值格式完全一致：(总资产, 现金, 银行, 股票)

#### 建议方案
**方案A：创建BaseService基类（推荐）**
```python
# base_service.py
import aiosqlite
from typing import Tuple

class BaseService:
    """服务基类，提供通用数据库操作方法"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    async def _get_user_asset(self, user_id: str) -> Tuple[int, int, int, int]:
        """获取用户资产（总资产、现金、银行、股票）"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT balance, bank_balance FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if not row:
                return (0, 0, 0, 0)
            
            cash = int(row[0]) if row[0] else 0
            bank = int(row[1]) if row[1] else 0
            
            # 计算股票市值
            cursor = await db.execute(
                """SELECT COALESCE(SUM(sh.remaining * sp.current_price), 0)
                   FROM stock_holdings sh
                   JOIN stock_prices sp ON sh.stock_name = sp.stock_name
                   WHERE sh.user_id = ? AND sh.remaining > 0 AND sp.delisted = 0""",
                (user_id,)
            )
            stock_row = await cursor.fetchone()
            stock = int(stock_row[0]) if stock_row and stock_row[0] else 0
        
        return (cash + bank + stock, cash, bank, stock)
    
    async def _user_exists(self, user_id: str) -> bool:
        """检查用户是否存在"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "SELECT 1 FROM users WHERE user_id = ?",
                (user_id,)
            )
            return await cursor.fetchone() is not None
```

**实施计划：**
1. 创建 `base_service.py` 文件
2. 将所有service继承 `BaseService`
3. 删除各service中的 `_get_user_asset` 方法
4. 测试所有功能

**预计收益：**
- 减少代码量：约150行
- 提高可维护性：统一修改只需改一处
- 减少bug风险：避免多处实现不一致

---

### 1.2 Service初始化代码重复

#### 问题描述
每个service都有完全相同的初始化代码。

#### 重复位置
所有13个service文件：
- admin_service.py
- announcement_service.py
- achievement_service.py
- bank_service.py
- shop_service.py
- work_service.py
- stock_service.py
- society_service.py
- signin_service.py
- stats_service.py
- tax_service.py
- tarot_service.py
- favor_system.py

#### 重复代码
```python
class XXXService:
    def __init__(self, db_path: str):
        self.db_path = db_path
```

#### 建议方案
使用BaseService基类统一初始化：
```python
# base_service.py
class BaseService:
    def __init__(self, db_path: str):
        self.db_path = db_path

# 其他service继承
class SocietyService(BaseService):
    def __init__(self, db_path: str):
        super().__init__(db_path)
        # 其他初始化...
```

---

### 1.3 获取富人阶级平均资产方法

#### 问题描述
获取前20%富人平均资产的方法在多个service中重复实现。

#### 重复位置

| 文件 | 行号 | 用途 |
|------|------|------|
| `society_service.py` | 211-237 | 千衢结社工资计算 |
| `work_service.py` | 259-290 | 工资加成计算 |

#### 建议方案
将方法移到 `stats_service.py`，其他service调用：
```python
# stats_service.py
async def get_rich_average_asset(self, percentile: float = 0.2) -> int:
    """获取前X%富人平均资产"""
    # 统一实现
```

---

## 2. Main.py中的重复造轮子

### 2.1 直接数据库操作

#### 问题描述
main.py中直接操作数据库，而这些操作应该由service层处理。

#### 具体位置

**位置1：获取或创建用户（_get_user）**
```python
# main.py 187-209行
async def _get_user(self, user_id: str) -> Dict:
    async with aiosqlite.connect(self.db_path) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        # ...
```

**问题：**
- 与 `signin_service.py` 中的 `_get_user()` 方法重复
- 应该在signin_service中统一处理用户获取/创建

**建议方案：**
```python
# 使用signin_service的方法替代
user = await self.signin_service._get_user(user_id)
```

---

**位置2：签到时更新税收分红**
```python
# main.py 326-331行
if tax_bonus > 0:
    async with aiosqlite.connect(self.db_path) as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (tax_bonus, user_id)
        )
        await db.commit()
```

**问题：**
- `tax_service.claim_tax_bonus()` 应该直接处理余额更新
- 不应该在main.py中直接操作数据库

**建议方案：**
修改 `tax_service.claim_tax_bonus()` 方法，使其直接更新用户余额：
```python
# tax_service.py
async def claim_tax_bonus(self, user_id: str) -> Tuple[int, int]:
    """领取税收分红，直接更新用户余额"""
    async with aiosqlite.connect(self.db_path) as db:
        # ... 计算分红 ...
        # 直接更新余额
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (bonus, user_id)
        )
        await db.commit()
    return bonus, remaining_pool
```

---

## 3. 工具函数使用情况分析

### 3.1 utils.py中的未使用函数

| 函数名 | 是否被使用 | 建议 |
|--------|-----------|------|
| `parse_amount()` | 未被使用 | 删除或保留备用 |
| `calculate_percentage()` | 未被使用 | 删除或保留备用 |
| `truncate_string()` | 未被使用 | 删除或保留备用 |

### 3.2 重复的时间获取逻辑

多个文件中直接调用 `datetime.now(timezone.utc)`，应该统一使用 `utils.get_beijing_time()`。

---

## 4. 数据库连接管理重复

### 4.1 问题描述
每个service都重复编写数据库连接代码：
```python
async with aiosqlite.connect(self.db_path) as db:
    # ... 操作
```

### 4.2 建议方案
在BaseService中提供通用方法：
```python
class BaseService:
    async def _execute(self, query: str, params: tuple = ()):
        """执行SQL查询"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            await db.commit()
            return cursor
    
    async def _fetchone(self, query: str, params: tuple = ()):
        """获取单条记录"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchone()
    
    async def _fetchall(self, query: str, params: tuple = ()):
        """获取所有记录"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            return await cursor.fetchall()
```

---

## 5. 实施优先级

### 高优先级（立即执行）
1. **创建BaseService基类**
   - 统一 `_get_user_asset()` 方法
   - 统一初始化代码
   - 预计减少代码：200+行

2. **修复main.py直接数据库操作**
   - 将 `_get_user()` 移到signin_service
   - 修改 `tax_service.claim_tax_bonus()` 直接更新余额
   - 预计减少main.py代码：50+行

### 中优先级（后续优化）
3. **统一数据库连接管理**
   - 在BaseService中添加通用查询方法
   - 逐步替换各service中的原始连接代码

4. **清理未使用的工具函数**
   - 删除或标记 `parse_amount()`, `calculate_percentage()`, `truncate_string()`

### 低优先级（可选）
5. **统一时间获取**
   - 确保所有模块使用 `utils.get_beijing_time()`

---

## 6. 预期收益

### 代码量减少
- 删除重复方法：约200行
- 简化main.py：约50行
- 统一初始化：约30行
- **总计：约280行**

### 可维护性提升
- 统一修改只需改一处
- 减少bug风险
- 代码结构更清晰
- 新service开发更简单（继承BaseService）

### 测试简化
- 只需测试BaseService的方法
- 各service的测试可以简化

---

## 7. 风险评估

### 低风险
- 创建BaseService并继承
- 删除未使用的工具函数

### 中风险
- 修改main.py的数据库操作（需要全面测试签到功能）
- 修改tax_service的claim_tax_bonus（需要测试税收分红）

### 建议实施顺序
1. 先创建BaseService，不删除原方法（保留兼容性）
2. 逐个service迁移到使用BaseService方法
3. 测试通过后删除原方法
4. 最后修改main.py
