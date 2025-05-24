#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
from web3 import Web3
from eth_typing import Address
from typing import Tuple

# 连接到以太坊网络（这里使用BSC主网）
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

# NonfungiblePositionManager合约地址（BSC主网）
POSITION_MANAGER_ADDRESS = '0x46A15B0b27311cedF172AB29E4f4766fbE7F4364'

# 加载ABI
with open('ABI/NonfungiblePositionManager.json', 'r') as f:
    position_manager_abi = json.load(f)

# 创建合约实例
position_manager = w3.eth.contract(
    address=Web3.to_checksum_address(POSITION_MANAGER_ADDRESS),
    abi=position_manager_abi
)

def get_unclaimed_fees(token_id: int) -> Tuple[int, int]:
    """
    获取指定tokenID上未提取的手续费数量
    
    Args:
        token_id: NFT的tokenID
        
    Returns:
        Tuple[int, int]: (token0未提取的手续费数量, token1未提取的手续费数量)
    """
    try:
        # 调用positions函数获取position信息
        position = position_manager.functions.positions(token_id).call()
        
        # 获取token0和token1的地址
        token0 = position[2]
        token1 = position[3]
        
        # 获取未提取的手续费
        fees = position_manager.functions.collect({
            'tokenId': token_id,
            'recipient': '0x0000000000000000000000000000000000000000',  # 零地址
            'amount0Max': 2**128 - 1,  # 最大值
            'amount1Max': 2**128 - 1   # 最大值
        }).call()
        
        return fees[0], fees[1]
        
    except Exception as e:
        print(f"获取手续费时发生错误: {str(e)}")
        return 0, 0

def main():
    if len(sys.argv) != 2:
        print("使用方法: python get_unclaimed_fees.py <token_id>")
        sys.exit(1)
        
    try:
        token_id = int(sys.argv[1])
        amount0, amount1 = get_unclaimed_fees(token_id)
        
        print(f"\nToken ID {token_id} 的未提取手续费:")
        print(f"Token0: {amount0}")
        print(f"Token1: {amount1}")
        
    except ValueError:
        print("错误: token_id 必须是有效的整数")
        sys.exit(1)

if __name__ == "__main__":
    main() 