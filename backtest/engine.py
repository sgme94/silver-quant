"""
回测引擎 - 历史数据回测
"""
import pandas as pd
from datetime import datetime
from typing import List, Dict
from tqdm import tqdm

from strategies.signal_strategies import get_strategy, Signal
from exchange.simulator import SimulatedExchange
from utils.data_fetcher import get_data_fetcher


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: dict):
        self.config = config
        self.strategy = None
        self.exchange = None
        self.data = None
        self.results = []
    
    def load_data(self, symbol: str = 'AG0', period: str = '5', 
                  start_date: str = None, end_date: str = None):
        """加载历史数据"""
        print(f"加载数据: {symbol}, 周期: {period}")
        
        fetcher = get_data_fetcher(self.config.get('data_source', 'mock'))
        df = fetcher.get_kline(symbol, period, count=2000)
        
        if df is None or df.empty:
            raise ValueError("无法获取数据")
        
        # 日期过滤
        if start_date:
            df = df[df['datetime'] >= start_date]
        if end_date:
            df = df[df['datetime'] <= end_date]
        
        self.data = df.reset_index(drop=True)
        print(f"加载完成: {len(self.data)} 条记录")
        print(f"时间范围: {self.data['datetime'].min()} ~ {self.data['datetime'].max()}")
        
        return self
    
    def set_strategy(self, strategy_name: str, **params):
        """设置策略"""
        self.strategy = get_strategy(strategy_name, **params)
        print(f"策略: {self.strategy.name}, 参数: {params}")
        return self
    
    def run(self) -> Dict:
        """执行回测"""
        if self.strategy is None:
            raise ValueError("请先设置策略")
        if self.data is None:
            raise ValueError("请先加载数据")
        
        print("\n开始回测...")
        
        # 初始化模拟交易所
        self.exchange = SimulatedExchange({
            'initial_capital': self.config.get('initial_capital', 1000000),
            'contract_unit': self.config.get('contract_unit', 15),
            'margin_ratio': self.config.get('margin_ratio', 0.12),
            'commission_rate': self.config.get('commission_rate', 0.00005)
        })
        
        # 计算策略信号（向量化计算）
        self.data = self.strategy.generate_signals(self.data)
        
        # 逐行模拟交易
        self.results = []
        for i in tqdm(range(len(self.data)), desc="回测中"):
            row = self.data.iloc[i]
            
            signal_value = row['signal']
            signal_str = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}.get(signal_value, 'HOLD')
            
            # 获取止损位
            stop_loss = None
            if 'stop_loss_long' in row and not pd.isna(row['stop_loss_long']):
                stop_loss = row['stop_loss_long']
            
            # 处理信号
            result = self.exchange.process_signal(
                row['datetime'], 
                signal_str, 
                row['close'],
                stop_loss
            )
            
            result['equity'] = self.exchange.account.get_equity(row['close'])
            self.results.append(result)
        
        # 强制平仓最后一笔
        if self.exchange.account.position != 0:
            final_price = self.data.iloc[-1]['close']
            self.exchange.account.close_position(
                self.data.iloc[-1]['datetime'],
                final_price,
                'end_of_data'
            )
        
        return self.get_report()
    
    def get_report(self) -> Dict:
        """生成回测报告"""
        final_price = self.data.iloc[-1]['close'] if self.data is not None else 0
        stats = self.exchange.account.get_stats(final_price)
        
        # 计算更多指标
        trades = self.exchange.account.trades
        closed_trades = [t for t in trades if t.exit_time is not None]
        
        # 计算最大回撤
        equity_curve = pd.DataFrame(self.results)
        if not equity_curve.empty and 'equity' in equity_curve.columns:
            equity_curve['peak'] = equity_curve['equity'].cummax()
            equity_curve['drawdown'] = (equity_curve['equity'] - equity_curve['peak']) / equity_curve['peak'] * 100
            max_drawdown = equity_curve['drawdown'].min()
        else:
            max_drawdown = 0
        
        # 计算夏普比率（简化）
        returns = []
        for i in range(1, len(equity_curve)):
            if equity_curve.iloc[i]['equity'] != 0:
                r = (equity_curve.iloc[i]['equity'] / equity_curve.iloc[i-1]['equity'] - 1) * 100
                returns.append(r)
        
        sharpe_ratio = 0
        if len(returns) > 1:
            import numpy as np
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            if std_return > 0:
                sharpe_ratio = (avg_return / std_return) * np.sqrt(252 * 48)  # 年化（5分钟线）
        
        report = {
            'summary': {
                'initial_capital': stats['initial_capital'],
                'final_equity': stats['current_equity'],
                'total_return': stats['total_return_pct'],
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'total_trades': stats['total_trades'],
                'win_rate': stats['win_rate'],
                'avg_win': stats['avg_win'],
                'avg_loss': stats['avg_loss'],
                'net_pnl': stats['net_pnl'],
                'total_commission': stats['total_commission']
            },
            'trades': closed_trades,
            'equity_curve': equity_curve.to_dict('records') if not equity_curve.empty else []
        }
        
        return report
    
    def print_report(self, report: Dict = None):
        """打印回测报告"""
        if report is None:
            report = self.get_report()
        
        s = report['summary']
        
        print("\n" + "="*50)
        print("回测报告")
        print("="*50)
        print(f"初始资金: {s['initial_capital']:,.0f} 元")
        print(f"最终权益: {s['final_equity']:,.0f} 元")
        print(f"总收益率: {s['total_return']:+.2f}%")
        print(f"最大回撤: {s['max_drawdown']:.2f}%")
        print(f"夏普比率: {s['sharpe_ratio']:.2f}")
        print(f"总交易次数: {s['total_trades']}")
        print(f"胜率: {s['win_rate']:.1f}%")
        print(f"平均盈利: {s['avg_win']:,.0f} 元")
        print(f"平均亏损: {s['avg_loss']:,.0f} 元")
        print(f"净盈亏: {s['net_pnl']:,.0f} 元")
        print(f"总手续费: {s['total_commission']:,.0f} 元")
        print("="*50)


if __name__ == '__main__':
    # 测试回测
    config = {
        'data_source': 'mock',
        'initial_capital': 1000000,
        'contract_unit': 15,
        'margin_ratio': 0.12,
        'commission_rate': 0.00005
    }
    
    engine = BacktestEngine(config)
    
    engine.load_data('AG0', '5')
    engine.set_strategy('dual_ma_atr', fast_ma=10, slow_ma=30, atr_period=14)
    report = engine.run()
    engine.print_report(report)
