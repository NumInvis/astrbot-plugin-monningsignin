# 莫宁宁的币 - AstrBot 经济系统插件 v1.0

[![GitHub stars](https://img.shields.io/github/stars/MTMASTER-star/astrbot-checkin-plugin-monningsignin?style=social)](https://github.com/MTMASTER-star/astrbot-checkin-plugin-monningsignin/stargazers)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

一个功能丰富的 AstrBot 经济系统插件，包含签到、银行、商店、股票、工作、结社、成就、好感度等多个子系统。

## ✨ 功能特性

### 💰 基础经济系统
- **签到系统** - 每日签到获取星声，连续签到有加成
- **银行系统** - 存款赚取利息，VIP用户免手续费
- **转账系统** - 用户间转账，支持@用户

### 🛍️ 商店与占卜
- **商店** - 购买各种道具和物品
- **背包** - 管理已购买的物品
- **占卜系统** - 使用占卜券进行运势占卜，最高66倍奖励

### 📈 股票系统
- **股市行情** - 实时查看股票价格
- **买卖股票** - 支持买入/卖出，有手续费
- **创立公司** - 用户可以创立自己的上市公司
- **公司管理** - 研发提升股价，宣告破产

### 💼 工作系统
- **找工作** - 查看各种工作岗位
- **应聘** - 选择心仪的工作
- **领工资** - 按工作时间领取工资

### 🏛️ 结社系统
- **结社列表** - 查看所有结社
- **加入结社** - 加入喜欢的结社获得福利
- **结社排行** - 查看各结社成员资产

### 🏆 成就系统
- **多种成就** - 蓝色、紫色、金色、彩色四个等级
- **成就加成** - 不同成就提供不同加成效果
- **永久保存** - 成就数据永久保存

### 💖 好感度系统
- **好感度计算** - 基于好感值的相对值
- **AI关系描述** - LLM自动生成关系描述
- **互动增加** - 与Bot互动增加好感值

## 📋 指令列表

### 普通用户指令

```
💰 基础：/签到 /余额 /转账 @用户 金额 /资产排行榜 /经济 /税收
🏦 银行：/银行 /存款 金额 /取款 金额
🛍️ 商店：/商店 /购买 商品 数量 /背包 /使用 物品 /占卜概率 /Allin
💼 工作：/找工作 /应聘 工作名 /工作状态 /领工资
📈 股票：/股市 /买入 股票 数量 /卖出 股票 数量 /持仓 /创立公司 名称 价格 描述 /宣告破产 公司 /研发 公司 金额 /股东 股票 /k线 股票
🏛️ 结社：/结社 /加入结社 名称 /我的结社
💖 好感：/好感度 /好感度排行
🏆 成就：/成就 /塔罗牌
```

### 管理员指令

```
系统：/admin reset 用户 /admin add 用户 金额 /admin remove 用户 金额 /admin clear
统计：/admin stats /admin users /admin logs
经济：/admin tax 税率 /admin bank 利率 /admin shop 商品 价格 数量
股票：/admin stock add 名称 价格 描述 /admin stock remove 名称 /admin stock price 名称 价格
商店：/admin shop add 商品名 价格 限购 好感值 描述 /admin shop remove 商品名 /admin shop edit 商品名 属性 值
好感：/admin favor add 用户 数量 /admin favor remove 用户 数量 /admin favor reset 用户
成就：/所有人成就 /授予成就 用户ID/所有人 成就ID /重置签到 用户ID/所有人
赛季：/新赛季 密码
```

## 🚀 安装方法

### 方法一：通过 AstrBot 插件市场安装（推荐）

1. 打开 AstrBot 管理面板
2. 进入插件市场
3. 搜索 "莫宁宁的币" 或 "经济系统"
4. 点击安装

### 方法二：手动安装

1. 克隆仓库到插件目录：
```bash
cd /path/to/astrbot/data/plugins
git clone https://github.com/MTMASTER-star/astrbot-checkin-plugin-monningsignin.git
```

2. 重启 AstrBot

## ⚙️ 配置说明

插件配置文件位于 `config.py`，可以修改以下配置：

- **税率设置** - 调整税收比例
- **银行利率** - 设置存款利率
- **商店商品** - 添加/修改商品
- **工作列表** - 添加新的工作岗位
- **结社配置** - 修改结社属性
- **塔罗牌效果** - 自定义塔罗牌效果

## 📝 更新日志

### v1.0 (2025-03-12) - 初始版本
- 🎉 项目正式发布
- ✅ 完整的经济系统：签到、银行、转账
- ✅ 商店系统：购买商品、背包管理
- ✅ 占卜系统：运势占卜，最高66倍奖励
- ✅ 股票系统：买卖股票、创立公司
- ✅ 工作系统：找工作、领工资
- ✅ 结社系统：加入结社、结社福利
- ✅ 成就系统：多等级成就、永久保存
- ✅ 好感度系统：互动增加好感度
- ✅ 公告系统：管理员发布公告
- ✅ 管理员功能：完整的后台管理指令

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的修改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 💖 致谢

- [AstrBot](https://github.com/Soulter/AstrBot) - 优秀的QQ机器人框架
- 所有贡献者和用户

## 📞 联系方式

- GitHub: [@MTMASTER-star](https://github.com/MTMASTER-star)
- 项目地址: https://github.com/MTMASTER-star/astrbot-checkin-plugin-monningsignin

---
