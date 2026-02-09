"""
策略模块 - 双均线 + ATR 趋势跟踪策略
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum


class Signal(Enum):
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class StrategyParams:
    """策略参数"""
    fast_ma: int = 10
    slow_ma: int = 30
    atr_period: int = 14
    atr_multiplier: float = 2.0
    # 过滤参数
    min_atr_ratio: float = 0.005  # 最小波动率要求 (ATR/Price)


class DualMA_ATR_Strategy:
    """
    双均线 + ATR 趋势跟踪策略
    
    逻辑：
    1. 快线上穿慢线 -> 做多信号
    2. 快线下穿慢线 -> 做空信号（或平多）
    3. ATR 过滤：波动率太低时不交易（避免震荡市频繁交易）
    4. 用 ATR 计算止损位
    """
    
    def __init__(self, params: StrategyParams = None):
        self.params = params or StrategyParams()
        self.name = "DualMA_ATR"
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算技术指标"""
        df = df.copy()
        
        # 双均线
        df['fast_ma'] = df['close'].rolling(self.params.fast_ma).mean()
        df['slow_ma'] = df['close'].rolling(self.params.slow_ma).mean()
        
        # ATR (Average True Range)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(self.params.atr_period).mean()
        
        # 波动率比率
        df['atr_ratio'] = df['atr'] / df['close']
        
        # 均线交叉信号
        df['ma_diff'] = df['fast_ma'] - df['slow_ma']
        df['cross_up'] = (df['ma_diff'] > 0) & (df['ma_diff'].shift(1) <= 0)
        df['cross_down'] = (df['ma_diff'] < 0) & (df['ma_diff'].shift(1) >= 0)
        
        # 止损位
        df['stop_loss_long'] = df['close'] - self.params.atr_multiplier * df['atr']
        df['stop_loss_short'] = df['close'] + self.params.atr_multiplier * df['atr']
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号"""
        df = self.calculate_indicators(df)
        
        df['signal'] = Signal.HOLD.value
        df['signal_price'] = np.nan
        df['stop_loss'] = np.nan
        
        for i in range(len(df)):
            if i < self.params.slow_ma:
                continue
            
            row = df.iloc[i]
            
            # ATR 过滤 - 波动率太低不交易
            if row['atr_ratio'] < self.params.min_atr_ratio:
                continue
            
            # 金叉买入
            if row['cross_up']:
                df.iloc[i, df.columns.get_loc('signal')] = Signal.BUY.value
                df.iloc[i, df.columns.get_loc('signal_price')] = row['close']
                df.iloc[i, df.columns.get_loc('stop_loss')] = row['stop_loss_long']
            
            # 死叉卖出
            elif row['cross_down']:
                df.iloc[i, df.columns.get_loc('signal')] = Signal.SELL.value
                df.iloc[i, df.columns.get_loc('signal_price')] = row['close']
                df.iloc[i, df.columns.get_loc('stop_loss')] = row['stop_loss_short']
        
        return df
    
    def get_latest_signal(self, df: pd.DataFrame) -> Dict:
        """获取最新信号"""
        df = self.generate_signals(df)
        latest = df.iloc[-1]
        
        signal_map = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}
        
        return {
            'timestamp': latest['datetime'] if 'datetime' in latest else None,
            'signal': signal_map.get(latest['signal'], 'HOLD'),
            'price': latest['close'],
            'fast_ma': latest['fast_ma'],
            'slow_ma': latest['slow_ma'],
            'atr': latest['atr'],
            'stop_loss': latest['stop_loss'] if not pd.isna(latest['stop_loss']) else None
        }


class RSIBollinger_Strategy:
    """
    RSI + 布林带 均值回归策略
    
    逻辑：
    1. 价格触及布林带下轨 + RSI < 30 -> 做多
    2. 价格触及布林带上轨 + RSI > 70 -> 做空/平多
    3. 价格回到布林带中轨 -> 平仓
    """
    
    def __init__(self, rsi_period=14, bb_period=20, bb_std=2):
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.name = "RSI_Bollinger"
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算指标"""
        df = df.copy()
        
        # 布林带
        df['bb_middle'] = df['close'].rolling(self.bb_period).mean()
        bb_std = df['close'].rolling(self.bb_period).std()
        df['bb_upper'] = df['bb_middle'] + self.bb_std * bb_std
        df['bb_lower'] = df['bb_middle'] - self.bb_std * bb_std
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df
    
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """生成信号"""
        df = self.calculate_indicators(df)
        
        df['signal'] = Signal.HOLD.value
        
        for i in range(len(df)):
            if i < self.bb_period:
                continue
            
            row = df.iloc[i]
            
            # 超卖买入
            if row['close'] <= row['bb_lower'] and row['rsi'] < 30:
                df.iloc[i, df.columns.get_loc('signal')] = Signal.BUY.value
            
            # 超买卖出
            elif row['close'] >= row['bb_upper'] and row['rsi'] > 70:
                df.iloc[i, df.columns.get_loc('signal')] = Signal.SELL.value
        
        return df
    
    def get_latest_signal(self, df: pd.DataFrame) -> Dict:
        """获取最新信号"""
        df = self.generate_signals(df)
        latest = df.iloc[-1]
        
        signal_map = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}
        
        return {
            'timestamp': latest['datetime'] if 'datetime' in latest else None,
            'signal': signal_map.get(latest['signal'], 'HOLD'),
            'price': latest['close'],
            'rsi': latest['rsi'],
            'bb_lower': latest['bb_lower'],
            'bb_upper': latest['bb_upper'],
            'bb_middle': latest['bb_middle']
        }


def get_strategy(name: str, **kwargs):
    """获取策略实例"""
    if name == 'dual_ma_atr':
        return DualMA_ATR_Strategy(StrategyParams(**kwargs))
    elif name == 'rsi_bollinger':
        return RSIBollinger_Strategy(**kwargs)
    else:
        return DualMA_ATR_Strategy()
