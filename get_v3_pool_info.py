import json
from web3 import Web3
from typing import List, Optional, Tuple, Dict
import signal
import sys
from tqdm import tqdm
from decimal import Decimal
import math

# BSC节点URL
BSC_NODE_URL = "https://bsc-dataseed.binance.org/"

# PancakeSwap V3 Factory合约地址
PANCAKESWAP_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

# ERC20 ABI
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# 全局变量用于控制程序退出
running = True

def signal_handler(signum, frame):
    """处理Ctrl+C信号"""
    global running
    print("\n正在安全退出程序...")
    running = False

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)

# 加载ABI
with open("ABI/PancakeV3Factory.json", "r") as f:
    FACTORY_ABI = json.load(f)

# 加载V3池子ABI
with open("ABI/PancakeV3Pool.json", "r") as f:
    POOL_ABI = json.load(f)

# 加载代币信息
with open("bsc_tokens.json", "r") as f:
    TOKENS = json.load(f)

def get_token_address(token_identifier: str) -> Optional[str]:
    """根据代币名称或符号获取地址，如果有多个匹配项，返回rank最小的"""
    matching_tokens = []
    for addr, info in TOKENS.items():
        if (info["name"].lower() == token_identifier.lower() or
            info["symbol"].lower() == token_identifier.lower()):
            matching_tokens.append((addr, info["rank"], info["name"], info["symbol"]))

    if not matching_tokens:
        return None

    # 按rank排序，返回rank最小的地址
    matching_tokens.sort(key=lambda x: x[1])
    selected_token = matching_tokens[0]
    print(f"找到代币: {selected_token[2]} ({selected_token[3]})")
    return selected_token[0]

def get_token_symbol(token_address: str) -> str:
    """获取代币符号"""
    # 尝试直接获取
    if token_address in TOKENS:
        return TOKENS[token_address]["symbol"]

    # 尝试大写地址
    token_address_upper = token_address.upper()
    if token_address_upper in TOKENS:
        return TOKENS[token_address_upper]["symbol"]

    # 尝试小写地址
    token_address_lower = token_address.lower()
    if token_address_lower in TOKENS:
        return TOKENS[token_address_lower]["symbol"]

    return token_address

def get_token_decimals(token_address: str, w3: Web3) -> int:
    """获取代币精度"""
    try:
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        return token_contract.functions.decimals().call()
    except Exception as e:
        print(f"获取代币精度时出错: {str(e)}")
        return 18  # 默认精度

def format_amount(amount: int, decimals: int) -> str:
    """格式化代币数量，考虑精度"""
    return str(Decimal(amount) / Decimal(10 ** decimals))

def calculate_liquidity_amounts(liquidity: int, sqrt_price_x96: int, tick: int) -> Tuple[float, float]:
    """计算当前价格下的代币数量"""
    # 将sqrt_price_x96转换为实际价格
    price = (Decimal(sqrt_price_x96) ** 2) / (Decimal(2) ** 192)
    sqrt_price = math.sqrt(float(price))

    # 计算当前tick对应的价格范围
    tick_lower = tick - 1
    tick_upper = tick + 1
    price_lower = 1.0001 ** tick_lower
    price_upper = 1.0001 ** tick_upper
    sqrt_price_lower = math.sqrt(price_lower)
    sqrt_price_upper = math.sqrt(price_upper)

    # 计算代币数量
    # 使用V3的流动性计算公式
    amount0 = float(liquidity) * (1/sqrt_price - 1/sqrt_price_upper)
    amount1 = float(liquidity) * (sqrt_price - sqrt_price_lower)

    return amount0, amount1

def get_pool_details(pool_address: str, w3: Web3) -> Dict:
    """获取池子的详细信息"""
    try:
        # 创建池子合约实例
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)

        # 获取基本信息
        token0 = pool.functions.token0().call()
        token1 = pool.functions.token1().call()
        fee = pool.functions.fee().call()

        # 获取当前价格信息
        slot0 = pool.functions.slot0().call()
        sqrt_price_x96 = slot0[0]
        tick = slot0[1]

        # 获取流动性信息
        liquidity = pool.functions.liquidity().call()

        # 获取协议费用信息
        protocol_fees = pool.functions.protocolFees().call()

        # 获取代币符号和精度
        token0_symbol = get_token_symbol(token0)
        token1_symbol = get_token_symbol(token1)
        token0_decimals = get_token_decimals(token0, w3)
        token1_decimals = get_token_decimals(token1, w3)

        # 计算实际价格
        price = (Decimal(sqrt_price_x96) ** 2) / (Decimal(2) ** 192)

        # 计算当前价格下的代币数量
        amount0, amount1 = calculate_liquidity_amounts(liquidity, sqrt_price_x96, tick)

        return {
            "address": pool_address,
            "token0": {
                "address": token0,
                "symbol": token0_symbol,
                "decimals": token0_decimals
            },
            "token1": {
                "address": token1,
                "symbol": token1_symbol,
                "decimals": token1_decimals
            },
            "fee": fee / 10000,  # 转换为百分比
            "current_price": float(price),
            "tick": tick,
            "liquidity": liquidity,
            "current_amounts": {
                "token0": amount0,
                "token1": amount1
            },
            "protocol_fees": {
                "token0": protocol_fees[0],
                "token1": protocol_fees[1]
            }
        }
    except Exception as e:
        print(f"获取池子 {pool_address} 详细信息时出错: {str(e)}")
        return None

def get_pool_info(token0_address: str, token1_address: str) -> List[Tuple[str, str, int]]:
    """获取两个代币之间的V3池子信息"""
    w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

    # 创建Factory合约实例
    factory = w3.eth.contract(address=Web3.to_checksum_address(PANCAKESWAP_V3_FACTORY), abi=FACTORY_ABI)

    # 生成费率列表：从0.01%到1%，步长0.05%
    fee_tiers = [100] + [int(fee * 500) for fee in range(1, 21)]  # 1(0.01%) + 5到100(0.05%到1%)

    pools = []
    # 使用tqdm创建进度条
    for fee in tqdm(fee_tiers, desc="扫描费率", unit="%", ncols=100):
        if not running:  # 检查是否需要退出
            break

        try:
            # 获取池子地址
            pool_address = factory.functions.getPool(
                Web3.to_checksum_address(token0_address),
                Web3.to_checksum_address(token1_address),
                fee
            ).call()

            if pool_address != "0x0000000000000000000000000000000000000000":
                # 获取池子详细信息
                pool_details = get_pool_details(pool_address, w3)
                if pool_details:
                    pools.append(pool_details)
        except Exception as e:
            print(f"\n获取费率 {fee/100}% 的池子信息时出错: {str(e)}")
            continue

    return pools

def main():
    try:
        # 获取用户输入
        token0_identifier = input("请输入第一个代币名称或符号: ")

        # 获取第一个代币地址
        token0_address = get_token_address(token0_identifier)
        if not token0_address:
            print(f"未找到名为 {token0_identifier} 的代币")
            return

        # 获取第二个代币输入
        token1_identifier = input("请输入第二个代币名称或符号 (直接回车默认使用WBNB): ")

        # 如果用户没有输入，默认使用WBNB
        if not token1_identifier:
            token1_address = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c"
            print("使用默认代币: WBNB")
        else:
            # 获取第二个代币地址
            token1_address = get_token_address(token1_identifier)
            if not token1_address:
                print(f"未找到名为 {token1_identifier} 的代币")
                return

        print(f"\n开始扫描V3池子信息...")
        pools = get_pool_info(token0_address, token1_address)

        if not running:  # 如果程序被中断，直接返回
            return

        if not pools:
            print(f"未找到V3池子")
            return

        # 打印池子详细信息
        print(f"\nV3池子详细信息:")
        for pool in pools:
            print(f"\n池子地址: {pool['address']}")
            print(f"交易对: {pool['token0']['symbol']}/{pool['token1']['symbol']}")
            print(f"费率: {pool['fee']}%")
            print(f"当前价格: {pool['current_price']}")
            print(f"当前Tick: {pool['tick']}")
            print(f"流动性: {pool['liquidity']} (当前价格下的估算代币数量)")
            print(f"当前价格下的代币数量:")
            print(f"  - {pool['token0']['symbol']}: {format_amount(pool['current_amounts']['token0'], pool['token0']['decimals'])}")
            print(f"  - {pool['token1']['symbol']}: {format_amount(pool['current_amounts']['token1'], pool['token1']['decimals'])}")
            print(f"累积的协议费用:")
            print(f"  - {pool['token0']['symbol']}: {format_amount(pool['protocol_fees']['token0'], pool['token0']['decimals'])}")
            print(f"  - {pool['token1']['symbol']}: {format_amount(pool['protocol_fees']['token1'], pool['token1']['decimals'])}")
            print("-" * 50)

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序发生错误: {str(e)}")
    finally:
        print("\n程序已退出")

if __name__ == "__main__":
    main()
