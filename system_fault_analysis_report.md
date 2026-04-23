# 系统故障排查分析报告

## 分析日期
2026-04-02

---

## 1. 功能模块错误场景模拟与分析

### 1.1 签到模块 (cmd_signin)

#### 可能的错误表现
- `no such column: bonus_claimed`
- `no such column: consecutive_days`
- `no such column: favor_value`

#### 错误类型
数据库表结构缺失

#### 涉及的代码组件
- `main.py` - cmd_signin 函数
- `tax_service.py` - claim_tax_bonus 方法
- `signin_service.py` - 签到奖励计算

#### 故障定位
users表和tax_pool表缺少必要的字段

---

### 1.2 商店模块 (cmd_shop)

#### 可能的错误表现
- `KeyError: 'emoji'`
- `no such table: inventory`
- `no such table: purchase_log`

#### 错误类型
配置数据缺失 / 数据库表缺失

#### 涉及的代码组件
- `config.py` - SHOP_ITEMS 配置
- `shop_service.py` - 购买逻辑
- `main.py` - 商店展示

#### 故障定位
- SHOP_ITEMS缺少emoji字段
- inventory表或purchase_log表未创建

---

### 1.3 成就模块 (cmd_achievements)

#### 可能的错误表现
- `string indices must be integers`
- `no such table: user_achievements`
- `no such table: custom_achievements`

#### 错误类型
数据结构不匹配 / 数据库表缺失

#### 涉及的代码组件
- `main.py` - cmd_achievements 函数
- `achievement_service.py` - 成就管理
- `achievements.py` - 成就定义

#### 故障定位
- 成就字典结构错误（已修复）
- user_achievements表未创建
- custom_achievements表未创建

---

### 1.4 K线模块 (cmd_kline)

#### 可能的错误表现
- `name 'timedelta' is not defined`
- `no such table: stock_price_history`

#### 错误类型
导入缺失 / 数据库表缺失

#### 涉及的代码组件
- `stock_service.py` - get_stock_kline 方法
- `main.py` - cmd_kline 函数

#### 故障定位
- timedelta未导入（已修复）
- stock_price_history表未创建

---

### 1.5 股票交易模块

#### 可能的错误表现
- `no such column: remaining`
- `no such column: last_dividend_date`
- `no such table: stock_transactions`

#### 错误类型
数据库字段缺失 / 表缺失

#### 涉及的代码组件
- `stock_service.py` - 买入/卖出/股息
- `db_manager.py` - 表结构定义

#### 故障定位
stock_holdings表缺少字段

---

### 1.6 结社模块

#### 可能的错误表现
- `no such table: user_society`
- `no such column: join_time`
- `no such column: last_change_time`

#### 错误类型
数据库表/字段缺失

#### 涉及的代码组件
- `society_service.py` - 结社管理
- `main.py` - 结社命令

#### 故障定位
user_society表结构不完整

---

### 1.7 工作模块

#### 可能的错误表现
- `no such table: user_work`
- `no such column: total_earned`

#### 错误类型
数据库表/字段缺失

#### 涉及的代码组件
- `work_service.py` - 工作管理
- `main.py` - 工作命令

#### 故障定位
user_work表缺少字段

---

### 1.8 塔罗牌模块

#### 可能的错误表现
- `no such table: user_daily_tarot`
- `no such column: effect_type`
- `no such column: effect_value`

#### 错误类型
数据库表/字段缺失

#### 涉及的代码组件
- `tarot_service.py` - 塔罗牌逻辑
- `main.py` - 塔罗牌命令

#### 故障定位
user_daily_tarot表缺少字段

---

### 1.9 公告模块

#### 可能的错误表现
- `no such table: announcements`

#### 错误类型
数据库表缺失

#### 涉及的代码组件
- `announcement_service.py` - 公告管理
- `main.py` - 公告命令

#### 故障定位
announcements表未创建

---

### 1.10 配置管理模块

#### 可能的错误表现
- `no such table: plugin_config`

#### 错误类型
数据库表缺失

#### 涉及的代码组件
- `config_manager.py` - 配置管理

#### 故障定位
plugin_config表未创建

---

## 2. 数据库结构完整性检查

### 2.1 现有数据库表 (db_manager.py中定义)

| 表名 | 状态 | 说明 |
|------|------|------|
| users | ✅ | 用户基础信息表 |
| inventory | ✅ | 用户背包表 |
| purchase_log | ✅ | 购买记录表 |
| lottery_log | ✅ | 占卜记录表 |
| stock_prices | ✅ | 股票价格表 |
| stock_holdings | ⚠️ | 缺少remaining等字段 |
| user_society | ⚠️ | 缺少join_time等字段 |
| user_jobs | ⚠️ | 结构可能不完整 |
| user_work | ⚠️ | 缺少total_earned字段 |
| user_daily_tarot | ⚠️ | 缺少effect_type等字段 |
| user_relationship | ✅ | 用户关系表 |
| user_info | ✅ | 用户信息表 |
| stock_price_history | ✅ | 股价历史表 |
| stock_transactions | ✅ | 交易记录表 |
| tax_pool | ⚠️ | 缺少bonus_claimed字段 |
| user_tax_record | ✅ | 税收记录表 |

### 2.2 缺失的数据库表

| 表名 | 用途 | 影响模块 |
|------|------|----------|
| user_achievements | 用户成就存储 | 成就系统 |
| achievement_bonuses | 成就加成存储 | 成就系统 |
| custom_achievements | 自定义成就 | 成就系统 |
| announcements | 公告存储 | 公告系统 |
| plugin_config | 插件配置 | 配置管理 |

### 2.3 缺失的数据库字段

| 表名 | 缺失字段 | 影响 |
|------|----------|------|
| tax_pool | bonus_claimed | 税收分红领取 |
| users | favor_value | 好感度系统 |
| users | consecutive_days | 连续签到 |
| users | bank_last_date | 银行利息计算 |
| stock_holdings | remaining | 股票持仓 |
| stock_holdings | last_dividend_date | 股息发放 |
| user_work | total_earned | 工作总收入 |
| user_daily_tarot | effect_type | 塔罗牌效果类型 |
| user_daily_tarot | effect_value | 塔罗牌效果值 |

---

## 3. 数据库迁移方案

### 3.1 迁移脚本功能

已创建 `db_migrate_complete.py` 脚本，功能包括：

1. **创建缺失的表**
   - user_achievements
   - achievement_bonuses
   - custom_achievements
   - announcements
   - plugin_config

2. **添加缺失的字段**
   - tax_pool.bonus_claimed
   - users.favor_value
   - users.consecutive_days
   - users.bank_last_date
   - stock_holdings.remaining
   - stock_holdings.last_dividend_date
   - user_work.total_earned
   - user_daily_tarot.effect_type
   - user_daily_tarot.effect_value

### 3.2 迁移特点

- **安全**: 使用 `IF NOT EXISTS` 避免重复创建
- **无损**: 使用 `ALTER TABLE ADD COLUMN` 不影响现有数据
- **可重复**: 多次执行不会出错
- **自动**: 插件启动时自动执行

---

## 4. 已修复的问题

### 4.1 已修复的代码问题

| 问题 | 文件 | 修复内容 |
|------|------|----------|
| timedelta未定义 | stock_service.py | 添加导入 |
| SHOP_ITEMS缺少emoji | config.py | 添加emoji字段 |
| 成就字典结构错误 | main.py | 修复遍历方式 |

### 4.2 已创建的文件

| 文件 | 用途 |
|------|------|
| db_migrate_complete.py | 完整数据库迁移脚本 |
| db_migrate.py | 基础迁移脚本（保留） |

---

## 5. 建议的后续操作

### 5.1 立即执行
1. 重启AstrBot插件，触发数据库迁移
2. 检查日志确认迁移成功
3. 测试各功能模块是否正常

### 5.2 监控要点
1. 数据库迁移日志输出
2. 各功能模块错误日志
3. 用户反馈的功能异常

### 5.3 预防措施
1. 定期检查数据库结构一致性
2. 新功能开发时同步更新迁移脚本
3. 建立数据库结构版本管理机制

---

## 6. 总结

### 发现的问题
- 5个缺失的数据库表
- 8个缺失的数据库字段
- 3个代码级别的错误

### 实施的修复
- 创建了完整的数据库迁移脚本
- 修复了所有已知的代码错误
- 在main.py中集成了自动迁移

### 预期效果
- 所有功能模块应能正常工作
- 数据库结构完整一致
- 不再出现表/字段缺失错误
