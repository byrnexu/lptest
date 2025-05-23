import json
from web3 import Web3
from typing import List, Optional, Tuple
import signal
import sys
from tqdm import tqdm

# BSC节点URL
BSC_NODE_URL = "https://bsc-dataseed.binance.org/"

# PancakeSwap V3 Factory合约地址
PANCAKESWAP_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

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
with open("ABI/PancakeV3Factory.ABI", "r") as f:
    FACTORY_ABI = json.load(f)

# V3池子的ABI
POOL_ABI = [
    {
        "inputs": [],
        "name": "token0",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token1",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]

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

def get_pool_info(token0_address: str, token1_address: str) -> List[Tuple[str, str, int]]:
    """获取两个代币之间的V3池子信息"""
    w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

    # 创建Factory合约实例
    factory = w3.eth.contract(address=Web3.to_checksum_address(PANCAKESWAP_V3_FACTORY), abi=FACTORY_ABI)

    # 生成费率列表：从0.01%到1%，步长0.01%
    fee_tiers = [int(fee * 100) for fee in range(1, 101)]  # 1到100，对应0.01%到1%

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
                # 创建池子合约实例
                pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)

                try:
                    # 获取代币地址
                    pool_token0 = pool.functions.token0().call()
                    pool_token1 = pool.functions.token1().call()

                    # 获取代币符号
                    token0_symbol = get_token_symbol(pool_token0)
                    token1_symbol = get_token_symbol(pool_token1)

                    # 确定代币顺序
                    is_token0_first = pool_token0.lower() == token0_address.lower()
                    pair_name = f"{token0_symbol}/{token1_symbol}" if is_token0_first else f"{token1_symbol}/{token0_symbol}"

                    pools.append((pool_address, pair_name, fee))
                except Exception as e:
                    print(f"\n获取池子 {pool_address} 信息时出错: {str(e)}")
                    continue
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

        # 打印池子信息
        print(f"\nV3池子信息:")
        for pool_address, pair_name, fee in pools:
            print(f"{pool_address} {pair_name} {fee/10000}%")

    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序发生错误: {str(e)}")
    finally:
        print("\n程序已退出")

if __name__ == "__main__":
    main()
