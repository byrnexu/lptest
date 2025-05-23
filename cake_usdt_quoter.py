from web3 import Web3
from eth_typing import Address
from typing import Tuple
import json

# 连接到BSC网络
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed4.binance.org/'))

# MixedRouteQuoterV1合约地址 (V3版本)
QUOTER_ADDRESS = '0x678Aa4bF4E210cf2166753e054d5b7c31cc7fa86'

# 加载ABI
try:
    with open('ABI/MixedRouteQuoterV1.json', 'r') as f:
        quoter_abi = json.load(f)
except Exception as e:
    print(f"加载ABI文件失败: {str(e)}")
    exit(1)

# 创建合约实例
quoter_contract = w3.eth.contract(address=QUOTER_ADDRESS, abi=quoter_abi)

def get_quote_v3(
    token_in: str,
    token_out: str,
    amount_in: int,
    fee: int = 2500,  # 默认0.3%费率
    sqrt_price_limit_x96: int = 0  # 0表示不限制价格
) -> Tuple[int, int, int, int]:
    """
    获取V3单一路径的报价

    参数:
        token_in: 输入代币地址
        token_out: 输出代币地址
        amount_in: 输入代币数量（以最小单位计）
        fee: 交易费率（例如：3000表示0.3%）
        sqrt_price_limit_x96: 价格限制

    返回:
        amount_out: 输出代币数量
        sqrt_price_x96_after: 交易后的价格
        initialized_ticks_crossed: 跨越的tick数量
        gas_estimate: 预估gas费用
    """
    params = {
        'tokenIn': token_in,
        'tokenOut': token_out,
        'amountIn': amount_in,
        'fee': fee,
        'sqrtPriceLimitX96': sqrt_price_limit_x96
    }

    try:
        print(f"正在查询报价...")
        print(f"参数: {params}")
        result = quoter_contract.functions.quoteExactInputSingleV3(params).call()
        return result
    except Exception as e:
        print(f"获取报价失败: {str(e)}")
        print(f"请检查:")
        print(f"1. 合约地址是否正确: {QUOTER_ADDRESS}")
        print(f"2. 代币地址是否正确: {token_in} -> {token_out}")
        print(f"3. 交易对是否存在且具有足够的流动性")
        return None

def main():
    # CAKE地址
    CAKE = "0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82"
    # USDT地址
    USDT = "0x55d398326f99059fF775485246999027B3197955"

    print(f"网络连接状态: {'已连接' if w3.is_connected() else '未连接'}")
    print(f"当前区块高度: {w3.eth.block_number}")

    # 输入1 CAKE (18位小数)
    amount_in = 1 * 10**18

    # 获取报价 (CAKE -> USDT)
    print("\n查询 CAKE -> USDT 报价...")
    result = get_quote_v3(
        token_in=CAKE,
        token_out=USDT,
        amount_in=amount_in,
        fee=2500 # 0.3%费率
    )

    if result:
        amount_out, sqrt_price_after, ticks_crossed, gas_estimate = result
        print(f"输入: 1 CAKE")
        print(f"输出数量: {amount_out / 10**18} USDT")
        print(f"交易后价格: {sqrt_price_after}")
        print(f"跨越的tick数量: {ticks_crossed}")
        print(f"预估gas费用: {gas_estimate}")

    # 反向获取报价 (USDT -> CAKE)
    amount_in_usdt = 1 * 10**18  # 1 USDT

    print("\n查询 USDT -> CAKE 报价...")
    result_reverse = get_quote_v3(
        token_in=USDT,
        token_out=CAKE,
        amount_in=amount_in_usdt,
        fee=2500 # 0.3%费率
    )

    if result_reverse:
        amount_out, sqrt_price_after, ticks_crossed, gas_estimate = result_reverse
        print(f"输入: 1 USDT")
        print(f"输出数量: {amount_out / 10**18} CAKE")
        print(f"交易后价格: {sqrt_price_after}")
        print(f"跨越的tick数量: {ticks_crossed}")
        print(f"预估gas费用: {gas_estimate}")

if __name__ == "__main__":
    main()
