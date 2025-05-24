#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from web3 import Web3
from eth_typing import Address
from typing import Tuple, Dict, Any
from decimal import Decimal

# 连接到以太坊网络（这里使用BSC主网）
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

# NonfungiblePositionManager合约地址（BSC主网）
POSITION_MANAGER_ADDRESS = '0x46A15B0b27311cedF172AB29E4f4766fbE7F4364'

# 加载ABI
with open('ABI/NonfungiblePositionManager.json', 'r') as f:
    position_manager_abi = json.load(f)

# 加载token信息
with open('bsc_tokens.json', 'r') as f:
    tokens_info = json.load(f)

# 创建合约实例
position_manager = w3.eth.contract(
    address=Web3.to_checksum_address(POSITION_MANAGER_ADDRESS),
    abi=position_manager_abi
)

def get_token_info(token_address: str) -> Dict[str, Any]:
    """
    获取token的信息
    
    Args:
        token_address: token的合约地址
        
    Returns:
        Dict包含token的名称、符号和精度信息
    """
    # 将地址转换为小写以匹配JSON文件中的格式
    # token_address = token_address.lower()
    print(f"\n正在查找代币地址: {token_address}")
    
    # 检查地址是否在tokens_info中
    if token_address in tokens_info:
        print(f"找到代币信息: {tokens_info[token_address]}")
        return tokens_info[token_address]
    
    # 如果没有找到，打印所有可用的token地址以供参考
    print("未找到代币信息，以下是部分可用的代币地址:")
    for addr in list(tokens_info.keys())[:5]:  # 只打印前5个作为示例
        print(f"- {addr}")
    
    return {
        "name": "未知代币",
        "symbol": "未知",
        "decimals": 18  # 默认精度为18
    }

def format_token_amount(amount: int, decimals: int) -> str:
    """
    将token数量转换为可读格式
    
    Args:
        amount: token的原始数量
        decimals: token的精度
        
    Returns:
        格式化后的token数量字符串
    """
    if amount == 0:
        return "0"
    
    # 使用Decimal进行精确计算
    decimal_amount = Decimal(amount) / Decimal(10 ** decimals)
    return f"{decimal_amount:,.8f}".rstrip('0').rstrip('.')

def get_unclaimed_fees(token_id: int) -> Tuple[int, int, str, str, int, int]:
    """
    获取指定tokenID上未提取的手续费数量
    
    Args:
        token_id: NFT的tokenID
        
    Returns:
        Tuple包含:
        - token0未提取的手续费数量
        - token1未提取的手续费数量
        - token0的符号
        - token1的符号
        - token0的精度
        - token1的精度
    """
    try:
        # 调用positions函数获取position信息
        position = position_manager.functions.positions(token_id).call()
        
        print("\n持仓详细信息:")
        print(f"防重放攻击值(nonce): {position[0]}")
        print(f"操作者地址(operator): {position[1]}")
        print(f"代币0地址(token0): {position[2]}")
        print(f"代币1地址(token1): {position[3]}")
        print(f"交易费率(fee): {position[4]} (例如：3000表示0.3%)")
        print(f"价格下限(tickLower): {position[5]}")
        print(f"价格上限(tickUpper): {position[6]}")
        print(f"流动性数量(liquidity): {position[7]}")
        print(f"代币0累计手续费增长率: {position[8]}")
        print(f"代币1累计手续费增长率: {position[9]}")
        print(f"未提取的代币0数量: {position[10]}")
        print(f"未提取的代币1数量: {position[11]}")
        
        # 获取token0和token1的地址
        token0 = position[2]
        token1 = position[3]
        
        print(f"\n代币地址信息:")
        print(f"代币0地址: {token0}")
        print(f"代币1地址: {token1}")
        
        # 获取token信息
        token0_info = get_token_info(token0)
        token1_info = get_token_info(token1)
        
        # 获取未提取的手续费
        fees = position_manager.functions.collect({
            'tokenId': token_id,
            'recipient': '0x0000000000000000000000000000000000000000',  # 零地址
            'amount0Max': 2**128 - 1,  # 最大值
            'amount1Max': 2**128 - 1   # 最大值
        }).call()
        
        return (
            fees[0], fees[1],
            token0_info['symbol'],
            token1_info['symbol'],
            token0_info['decimals'],
            token1_info['decimals']
        )
        
    except Exception as e:
        print(f"获取手续费时发生错误: {str(e)}")
        return 0, 0, "未知", "未知", 18, 18

def main():
    if len(sys.argv) != 2:
        print("使用方法: python get_unclaimed_fees.py <token_id>")
        sys.exit(1)
        
    try:
        token_id = int(sys.argv[1])
        amount0, amount1, symbol0, symbol1, decimals0, decimals1 = get_unclaimed_fees(token_id)
        
        print(f"\nToken ID {token_id} 的未提取手续费:")
        print(f"{symbol0}: {format_token_amount(amount0, decimals0)}")
        print(f"{symbol1}: {format_token_amount(amount1, decimals1)}")
        
    except ValueError:
        print("错误: token_id 必须是有效的整数")
        sys.exit(1)

if __name__ == "__main__":
    main()
