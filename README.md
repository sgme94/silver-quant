# Silver Quant - 白银期货量化交易系统

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

基于 Python + Backtrader 的量化交易回测系统，专为国内白银期货（SHFE AG）设计。

## 特点

- 双均线 + ATR 趋势跟踪策略
- 信号强度评估（0-100分）
- 实时监控面板
- 自动通知高确定性交易机会
- 完整的回测报告（夏普比率、最大回撤等）

## 快速开始

```bash
pip install -r requirements.txt
python main.py backtest
```

## 回测结果示例

| 指标 | 数值 |
|------|------|
| 初始资金 | 20万 |
| 总收益率 | +23.38% |
| 夏普比率 | 5.25 |
| 最大回撤 | -7.03% |
| 胜率 | 37.5% |

## 使用

```bash
# 回测
python main.py backtest

# 模拟实盘
python main.py paper --duration 60

# 查看信号
python main.py signal

# 监控账户
python monitor.py status
```

## 项目结构

```
silver-quant/
├── strategies/      # 策略模块
├── backtest/        # 回测引擎
├── exchange/        # 模拟交易所
├── utils/           # 工具函数
├── main.py          # 主程序
└── config.yaml      # 配置文件
```

## License

MIT

## 支持

如果这个项目对你有帮助，欢迎 Star ⭐️ 或微信打赏支持！
微信打赏二维码：
<img width="717" height="771" alt="image" src="https://github.com/user-attachments/assets/8c44e7d0-812a-4bbd-99a6-f4fc7fd5b5bf" />

## 支持

如果这个项目对你有帮助，欢迎 [打赏支持](SPONSOR.md)！
