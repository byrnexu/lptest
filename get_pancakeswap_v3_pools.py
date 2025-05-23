from web3 import Web3
import json
from typing import List, Dict
import time
import os
import signal
import sys
import argparse
from web3.middleware import geth_poa_middleware
from requests.exceptions import Timeout, ConnectionError
import random

# 解析命令行参数
parser = argparse.ArgumentParser(description='获取PancakeSwap V3 LP池信息')
parser.add_argument('--restart', action='store_true', help='从头开始重新获取数据')
args = parser.parse_args()

# 全局变量用于控制程序运行
running = True

def signal_handler(signum, frame):
    """
    处理中断信号
    """
    global running
    print("\n正在优雅退出...")
    running = False

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 加载BSC代币信息
def load_bsc_tokens() -> Dict:
    """
    加载BSC代币信息
    """
    try:
        with open('bsc_tokens.json', 'r') as f:
            tokens = json.load(f)
            # 创建地址到代币信息的映射，确保地址格式一致
            token_map = {}
            for address, token_info in tokens.items():
                try:
                    # 确保地址是checksum格式
                    address = Web3.to_checksum_address(address)
                    token_map[address.lower()] = token_info
                except Exception as e:
                    print(f"处理代币地址时出错: {address} - {str(e)}")
            print(f"成功加载 {len(token_map)} 个代币信息")
            return token_map
    except Exception as e:
        print(f"加载BSC代币信息失败: {str(e)}")
        return {}

# 使用更多的RPC节点
RPC_URLS = [
    'https://bsc-dataseed1.defibit.io/',
    'https://bsc-dataseed1.ninicoin.io/',
    'https://bsc-dataseed.binance.org/',
    'https://bsc-dataseed2.defibit.io/',
    'https://bsc-dataseed3.defibit.io/',
    'https://bsc-dataseed4.defibit.io/',
    'https://bsc-dataseed2.ninicoin.io/',
    'https://bsc-dataseed3.ninicoin.io/',
    'https://bsc-dataseed4.ninicoin.io/',
    'https://bsc-dataseed1.binance.org/',
    'https://bsc-dataseed2.binance.org/',
    'https://bsc-dataseed3.binance.org/',
    'https://bsc-dataseed4.binance.org/'
]

class Web3Provider:
    def __init__(self):
        self.current_provider = None
        self.contract = None
        self.initialize_provider()

    def initialize_provider(self):
        """初始化Web3提供者"""
        # 随机打乱RPC节点列表
        random.shuffle(RPC_URLS)

        for url in RPC_URLS:
            try:
                w3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 30}))
                if w3.is_connected():
                    print(f"已连接到节点: {url}")
                    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                    self.current_provider = w3
                    self.contract = w3.eth.contract(
                        address=FACTORY_ADDRESS,
                        abi=factory_abi
                    )
                    return True
            except Exception as e:
                print(f"连接节点 {url} 失败: {str(e)}")
                continue
        return False

    def switch_provider(self):
        """切换到新的RPC节点"""
        print("正在切换到新的RPC节点...")
        return self.initialize_provider()

    def get_events(self, from_block: int, to_block: int) -> List[Dict]:
        """获取事件，带自动重试和节点切换"""
        max_retries = 3
        for attempt in range(max_retries):
            if not running:
                return []

            try:
                pool_created_filter = self.contract.events.PoolCreated.create_filter(
                    fromBlock=from_block,
                    toBlock=to_block
                )
                events = pool_created_filter.get_all_entries()
                return events
            except (Timeout, ConnectionError) as e:
                if not running:
                    return []

                if attempt < max_retries - 1:
                    print(f"获取区块 {from_block} 到 {to_block} 的事件时出错，正在重试 ({attempt + 1}/{max_retries})")
                    if not self.switch_provider():
                        print("无法切换到新的RPC节点，等待后重试...")
                    time.sleep(2)  # 增加重试等待时间
                else:
                    print(f"获取区块 {from_block} 到 {to_block} 的事件失败: {str(e)}")
                    return []
            except Exception as e:
                if not running:
                    return []

                if attempt < max_retries - 1:
                    print(f"获取区块 {from_block} 到 {to_block} 的事件时出错，正在重试 ({attempt + 1}/{max_retries})")
                    time.sleep(2)
                else:
                    print(f"获取区块 {from_block} 到 {to_block} 的事件失败: {str(e)}")
                    return []

# PancakeSwap V3 Factory合约地址
FACTORY_ADDRESS = '0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865'

# 加载Factory ABI
with open('ABI/PancakeV3Factory.json', 'r') as f:
    factory_abi = json.load(f)

# 创建Web3提供者实例
web3_provider = Web3Provider()

# 加载BSC代币信息
bsc_tokens = load_bsc_tokens()

def get_token_info(address: str) -> Dict:
    """
    获取代币信息
    """
    try:
        # 确保地址是checksum格式
        address = Web3.to_checksum_address(address)
        address_lower = address.lower()
        if address_lower in bsc_tokens:
            return bsc_tokens[address_lower]
        print(f"未找到代币信息: {address}")
        return {'symbol': 'Unknown', 'name': 'Unknown Token'}
    except Exception as e:
        print(f"处理代币地址时出错: {address} - {str(e)}")
        return {'symbol': 'Unknown', 'name': 'Unknown Token'}

def save_progress(current_block: int, pools: List[Dict]):
    """
    保存当前进度
    """
    progress = {
        'last_block': current_block,
        'pools': pools
    }
    with open('pools_progress.json', 'w') as f:
        json.dump(progress, f)

def load_progress() -> tuple:
    """
    加载上次的进度
    """
    if os.path.exists('pools_progress.json') and not args.restart:
        with open('pools_progress.json', 'r') as f:
            progress = json.load(f)
            return progress['last_block'], progress['pools']
    return None, []

def get_tick_spacing_value(tick_spacing: int) -> str:
    """
    计算 tickSpacing 的实际数值
    tickSpacing 为 1 时，价格变化约为 0.01%
    """
    # 计算价格变化百分比
    price_change = (1.0001 ** tick_spacing - 1) * 100
    return f"{price_change:.4f}%"

def save_known_pool(pool: Dict):
    """
    保存已知代币的LP池信息到文件
    """
    try:
        # 检查文件是否存在
        if os.path.exists('known_pools.json'):
            with open('known_pools.json', 'r') as f:
                known_pools = json.load(f)
        else:
            known_pools = []

        # 检查是否已存在相同的池
        pool_address = pool['pool'].lower()
        for existing_pool in known_pools:
            if existing_pool['pool'].lower() == pool_address:
                return  # 如果已存在，直接返回

        # 添加pair字段
        pool_with_pair = pool.copy()
        pool_with_pair['pair'] = f"{pool['token0_symbol']}/{pool['token1_symbol']}"

        # 添加新的池信息
        known_pools.append(pool_with_pair)

        # 按代币符号排序
        known_pools.sort(key=lambda x: (x['token0_symbol'], x['token1_symbol']))

        # 保存更新后的信息，使用更易读的格式
        with open('known_pools.json', 'w', encoding='utf-8') as f:
            json.dump(known_pools, f, indent=2, ensure_ascii=False, sort_keys=True)
    except Exception as e:
        print(f"保存已知池信息时出错: {str(e)}")

def print_pool_info(pool: Dict, index: int = None):
    """
    打印LP池信息
    """
    if index is not None:
        print(f"\n池 #{index}")
    print(f"Token0: {pool['token0']} ({pool['token0_symbol']} - {pool['token0_name']})")
    print(f"Token1: {pool['token1']} ({pool['token1_symbol']} - {pool['token1_name']})")
    print(f"手续费率: {pool['fee']/10000}%")
    tick_spacing_value = get_tick_spacing_value(pool['tickSpacing'])
    print(f"Tick间距: {pool['tickSpacing']} (价格变化: {tick_spacing_value})")
    print(f"池地址: {pool['pool']}")
    print("-" * 80)

    # 只检查代币的symbol是否为Unknown
    if pool['token0_symbol'] != 'Unknown' and pool['token1_symbol'] != 'Unknown':
        save_known_pool(pool)
        print(f"已保存到 known_pools.json: {pool['token0_symbol']}/{pool['token1_symbol']}")

def get_all_pools() -> List[Dict]:
    """
    获取所有PancakeSwap V3的LP池信息
    """
    # 获取当前区块高度
    current_block = web3_provider.current_provider.eth.block_number

    # Factory合约部署区块
    start_block = 26956207  # PancakeSwap V3 Factory部署区块 (2023-04-03)

    # 加载上次的进度
    last_block, pools = load_progress()
    if last_block and not args.restart:
        start_block = last_block + 1
        print(f"从上次的进度继续: 区块 {start_block}")
    else:
        print(f"从头开始获取: 区块 {start_block}")
        pools = []

    # 每次查询的区块范围
    block_range = 10000  # 进一步减小查询范围以提高成功率

    try:
        # 分批获取事件
        for from_block in range(start_block, current_block, block_range):
            if not running:
                print("\n检测到中断信号，正在保存进度...")
                save_progress(from_block - 1, pools)
                return pools

            to_block = min(from_block + block_range - 1, current_block)
            print(f"正在获取区块 {from_block} 到 {to_block} 的事件...")

            events = web3_provider.get_events(from_block, to_block)

            for event in events:
                token0_info = get_token_info(event['args']['token0'])
                token1_info = get_token_info(event['args']['token1'])

                pool_info = {
                    'token0': event['args']['token0'],
                    'token0_symbol': token0_info['symbol'],
                    'token0_name': token0_info['name'],
                    'token1': event['args']['token1'],
                    'token1_symbol': token1_info['symbol'],
                    'token1_name': token1_info['name'],
                    'fee': event['args']['fee'],
                    'tickSpacing': event['args']['tickSpacing'],
                    'pool': event['args']['pool']
                }
                pools.append(pool_info)
                # 实时打印找到的LP池信息
                print_pool_info(pool_info, len(pools))

            # 每完成一个范围就保存进度
            save_progress(to_block, pools)

            # 添加短暂延迟以避免请求过于频繁
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n检测到中断信号，正在保存进度...")
        save_progress(from_block - 1, pools)
        return pools

    return pools

def main():
    print("开始获取PancakeSwap V3 LP池信息...")
    print("按 Ctrl+C 可以随时中断程序，进度会被保存")

    try:
        pools = get_all_pools()

        if not running:
            print("\n程序已中断，已保存当前进度")
            return

        print(f"\n总共找到 {len(pools)} 个LP池")

        # 保存最终结果
        with open('pancakeswap_v3_pools.json', 'w') as f:
            json.dump(pools, f, indent=2)
        print("\n结果已保存到 pancakeswap_v3_pools.json")

    except KeyboardInterrupt:
        print("\n程序已中断，已保存当前进度")
    except Exception as e:
        print(f"\n程序出错: {str(e)}")
        print("已保存当前进度")

if __name__ == "__main__":
    main()
