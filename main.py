#!/usr/bin/env python3
"""
白银期货量化交易系统 - 主程序
"""
import sys
import time
import yaml
import argparse
import pandas as pd
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest.engine import BacktestEngine
from utils.data_fetcher import get_data_fetcher
from strategies.signal_strategies import get_strategy
from exchange.simulator import SimulatedExchange, Account


def load_config():
    """加载配置"""
    config_path = Path(__file__).parent / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def run_backtest(config):
    """运行回测模式"""
    print("="*60)
    print("白银期货量化回测系统")
    print("="*60)
    
    engine = BacktestEngine({
        'data_source': config['data']['source'],
        'initial_capital': config['account']['initial_capital'],
        'contract_unit': config['exchange']['contract_unit'],
        'margin_ratio': config['exchange']['margin_ratio'],
        'commission_rate': config['exchange']['commission_rate'],
        'max_trades_per_day': config['account'].get('max_trades_per_day', 10)
    })
    
    # 加载数据
    engine.load_data(
        symbol='AG0',
        period=config['data']['interval']
    )
    
    # 设置策略
    strategy_config = config['strategy']
    engine.set_strategy(
        strategy_config['name'],
        **strategy_config.get('params', {})
    )
    
    # 运行回测
    report = engine.run()
    engine.print_report(report)
    
    return report


def run_paper_trading(config, duration_minutes=60):
    """运行模拟实盘模式"""
    print("="*60)
    print("白银期货模拟实盘交易")
    print("="*60)
    
    # 初始化
    exchange = SimulatedExchange({
        'initial_capital': config['account']['initial_capital'],
        'contract_unit': config['exchange']['contract_unit'],
        'margin_ratio': config['exchange']['margin_ratio'],
        'commission_rate': config['exchange']['commission_rate'],
        'max_trades_per_day': config['account'].get('max_trades_per_day', 10)
    }, data_dir='silver_quant/data')
    
    strategy = get_strategy(
        config['strategy']['name'],
        **config['strategy'].get('params', {})
    )
    
    fetcher = get_data_fetcher(config['data']['source'])
    
    # 加载历史数据用于计算指标
    print("加载历史数据...")
    hist_data = fetcher.get_kline('AG0', '5', count=200)
    
    # 显示初始状态
    print("\n【初始账户状态】")
    stats = exchange.get_account_summary()
    print(f"初始资金: {stats['initial_capital']:,.0f} 元")
    print(f"可用资金: {stats['cash']:,.0f} 元")
    print(f"今日可交易: {stats['max_trades_per_day'] - stats['today_trades']} 次")
    
    print(f"\n开始模拟交易，运行 {duration_minutes} 分钟...")
    print("运行中可随时运行 `python monitor.py status` 查看账户状态")
    print("按 Ctrl+C 停止\n")
    
    try:
        for i in range(duration_minutes):
            # 获取实时行情
            quote = fetcher.get_realtime_quote('AG0')
            if quote is None:
                print(f"[{datetime.now()}] 获取数据失败，跳过")
                time.sleep(60)
                continue
            
            # 更新历史数据
            new_row = {
                'datetime': datetime.strptime(quote['timestamp'], '%Y-%m-%d %H:%M:%S'),
                'open': quote['open'],
                'high': quote['high'],
                'low': quote['low'],
                'close': quote['price'],
                'volume': quote['volume']
            }
            
            # 使用历史数据 + 最新价格计算信号
            df = hist_data.copy()
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            signal_info = strategy.get_latest_signal(df)
            
            # 处理交易
            result = exchange.process_signal(
                new_row['datetime'], 
                signal_info['signal'],
                signal_info['price'],
                signal_info.get('stop_loss')
            )
            
            # 获取最新状态
            stats = exchange.get_account_summary(quote['price'])
            
            # 输出状态
            status_line = (f"[{new_row['datetime'].strftime('%H:%M')}] "
                  f"价格:{quote['price']:.0f} "
                  f"信号:{signal_info['signal']:6s} "
                  f"持仓:{stats['position']:2d}手 "
                  f"权益:{stats['current_equity']/10000:.2f}万 "
                  f"收益:{stats['total_return_pct']:+.2f}% "
                  f"今日交易:{stats['today_trades']}/{stats['max_trades_per_day']}")
            
            if result['action'] != 'NONE':
                status_line += f" | 执行:{result['action']}"
            
            print(status_line)
            
            time.sleep(60)  # 每分钟检查一次
            
    except KeyboardInterrupt:
        print("\n\n停止交易")
    
    # 最终报告
    print("\n" + "="*60)
    print("模拟交易报告")
    print("="*60)
    
    # 强制平仓
    if exchange.account.position != 0:
        quote = fetcher.get_realtime_quote('AG0')
        exchange.account.close_position(
            datetime.now(),
            quote['price'],
            'manual_close'
        )
        exchange._save_account()
    
    quote = fetcher.get_realtime_quote('AG0')
    stats = exchange.get_account_summary(quote['price'])
    print(f"最终权益: {stats['current_equity']:,.0f} 元")
    print(f"总收益率: {stats['total_return_pct']:+.2f}%")
    print(f"总交易次数: {stats['total_trades']}")
    print(f"胜率: {stats['win_rate']:.1f}%")
    print(f"净盈亏: {stats['net_pnl']:,.0f} 元")
    print("\n使用 `python monitor.py status` 查看详细账户信息")


def run_live_signal(config):
    """仅输出实时信号（不交易）"""
    print("="*60)
    print("白银期货实时信号")
    print("="*60)
    
    strategy = get_strategy(
        config['strategy']['name'],
        **config['strategy'].get('params', {})
    )
    
    fetcher = get_data_fetcher(config['data']['source'])
    
    # 加载历史数据
    hist_data = fetcher.get_kline('AG0', '5', count=100)
    
    quote = fetcher.get_realtime_quote('AG0')
    if quote:
        new_row = {
            'datetime': datetime.strptime(quote['timestamp'], '%Y-%m-%d %H:%M:%S'),
            'open': quote['open'],
            'high': quote['high'],
            'low': quote['low'],
            'close': quote['price'],
            'volume': quote['volume']
        }
        df = pd.concat([hist_data, pd.DataFrame([new_row])], ignore_index=True)
        
        signal_info = strategy.get_latest_signal(df)
        
        print(f"\n当前时间: {signal_info['timestamp']}")
        print(f"当前价格: {signal_info['price']:.2f} 元/千克")
        print(f"交易信号: {signal_info['signal']}")
        
        if 'fast_ma' in signal_info:
            print(f"\n技术指标:")
            print(f"  快线 MA: {signal_info['fast_ma']:.2f}")
            print(f"  慢线 MA: {signal_info['slow_ma']:.2f}")
            print(f"  ATR: {signal_info['atr']:.2f}")
            if signal_info['stop_loss']:
                print(f"  止损位: {signal_info['stop_loss']:.2f}")


def main():
    parser = argparse.ArgumentParser(description='白银期货量化交易系统')
    parser.add_argument('mode', choices=['backtest', 'paper', 'signal'],
                        help='运行模式: backtest=回测, paper=模拟实盘, signal=仅信号')
    parser.add_argument('--duration', type=int, default=60,
                        help='模拟实盘运行时长（分钟），默认60')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config()
    
    if args.mode == 'backtest':
        run_backtest(config)
    elif args.mode == 'paper':
        run_paper_trading(config, args.duration)
    elif args.mode == 'signal':
        run_live_signal(config)


if __name__ == '__main__':
    main()
