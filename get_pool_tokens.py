"""
PancakeSwap V3 池子代币数量查询工具

功能说明：
1. 根据两个代币的地址和费率，查询对应的PancakeSwap V3池子
2. 获取池子中两个代币的总量
3. 获取池子历史手续费

使用方法：
1. 确保已安装web3库：pip install web3 tqdm
2. 修改代码中的token0_address、token1_address和fee参数
3. 运行脚本即可获取池子中的代币数量和手续费信息

参数说明：
- token0_address: 第一个代币的合约地址
- token1_address: 第二个代币的合约地址
- fee: 费率（例如：500表示0.05%，3000表示0.3%）

注意事项：
1. 确保代币地址正确
2. 费率必须是PancakeSwap V3支持的费率之一
3. 如果找不到对应的池子，会返回None
"""

from web3 import Web3
from web3.middleware import geth_poa_middleware
import json
from datetime import datetime, timedelta
from tqdm import tqdm

# 连接到BSC网络
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))
# 添加PoA中间件
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# 加载ABI
with open('ABI/PancakeV3Pool.json', 'r') as f:
    pool_abi = json.load(f)
with open('ABI/PancakeV3Factory.json', 'r') as f:
    factory_abi = json.load(f)

# ERC20代币的标准ABI
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

def get_pool_tokens(token0_address, token1_address, fee):
    """获取PancakeSwap V3池子中两个代币的总量"""
    # 获取池子地址
    factory_address = '0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865'
    factory_contract = w3.eth.contract(address=Web3.to_checksum_address(factory_address), abi=factory_abi)
    pool_address = factory_contract.functions.getPool(
        Web3.to_checksum_address(token0_address),
        Web3.to_checksum_address(token1_address),
        fee
    ).call()

    if pool_address == '0x0000000000000000000000000000000000000000':
        print("未找到对应的池子")
        return None, None

    # 创建合约实例
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
    token0_contract = w3.eth.contract(address=Web3.to_checksum_address(token0_address), abi=ERC20_ABI)
    token1_contract = w3.eth.contract(address=Web3.to_checksum_address(token1_address), abi=ERC20_ABI)

    # 获取代币精度
    token0_decimals = token0_contract.functions.decimals().call()
    token1_decimals = token1_contract.functions.decimals().call()

    # 获取池子中代币的总量
    total0 = token0_contract.functions.balanceOf(pool_address).call()
    total1 = token1_contract.functions.balanceOf(pool_address).call()

    return total0 / (10 ** token0_decimals), total1 / (10 ** token1_decimals)

def get_pool_fees(token0_address, token1_address, fee, days=7):
    """获取PancakeSwap V3池子过去一段时间的手续费"""
    print(f"\n开始查询过去{days}天的手续费...")
    
    # 获取池子地址
    factory_address = '0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865'
    factory_contract = w3.eth.contract(address=Web3.to_checksum_address(factory_address), abi=factory_abi)
    pool_address = factory_contract.functions.getPool(
        Web3.to_checksum_address(token0_address),
        Web3.to_checksum_address(token1_address),
        fee
    ).call()

    if pool_address == '0x0000000000000000000000000000000000000000':
        print("未找到对应的池子")
        return None, None

    # 创建合约实例
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)
    token0_contract = w3.eth.contract(address=Web3.to_checksum_address(token0_address), abi=ERC20_ABI)
    token1_contract = w3.eth.contract(address=Web3.to_checksum_address(token1_address), abi=ERC20_ABI)

    # 获取代币精度
    token0_decimals = token0_contract.functions.decimals().call()
    token1_decimals = token1_contract.functions.decimals().call()

    # 计算区块范围
    end_block = w3.eth.block_number
    # BSC每3秒一个区块
    blocks_per_day = (60 * 60 * 24) // 3  # 每天28800个区块
    start_block = end_block - (blocks_per_day * days)
    
    print(f"开始区块: {start_block}")
    print(f"结束区块: {end_block}")
    print(f"区块范围: {end_block - start_block}")

    # 将区块范围分成多个小段，每段最多50000个区块
    block_ranges = []
    current_start = start_block
    while current_start < end_block:
        current_end = min(current_start + 49999, end_block)
        block_ranges.append((current_start, current_end))
        current_start = current_end + 1

    print(f"\n将查询分成 {len(block_ranges)} 段进行...")

    # 计算总手续费
    total_fee0 = 0
    total_fee1 = 0
    
    for i, (range_start, range_end) in enumerate(block_ranges, 1):
        print(f"\n正在处理第 {i}/{len(block_ranges)} 段 (区块 {range_start} - {range_end})...")
        swap_filter = pool_contract.events.Swap.create_filter(fromBlock=range_start, toBlock=range_end)
        swap_events = swap_filter.get_all_entries()
        
        for event in tqdm(swap_events, desc=f"处理第 {i} 段事件"):
            # 计算手续费
            # 如果amount0为负，说明是token0的输入，手续费在amount0中
            # 如果amount1为负，说明是token1的输入，手续费在amount1中
            if event.args.amount0 < 0:  # token0输入
                fee_amount = abs(event.args.amount0) * fee / 1000000  # fee是万分比，需要除以1000000
                total_fee0 += fee_amount
            if event.args.amount1 < 0:  # token1输入
                fee_amount = abs(event.args.amount1) * fee / 1000000
                total_fee1 += fee_amount

    return total_fee0 / (10 ** token0_decimals), total_fee1 / (10 ** token1_decimals)

if __name__ == "__main__":
    # AIOT-USDT池子
    token0 = "0x55ad16Bd573B3365f43A9dAeB0Cc66A73821b4a5"  # AIOT
    token1 = "0x55d398326f99059fF775485246999027B3197955"  # USDT
    fee = 500  # 0.05%

    # 获取池子中代币的总量
    total0, total1 = get_pool_tokens(token0, token1, fee)
    if total0 is not None and total1 is not None:
        print(f"\n池子中代币总量:")
        print(f"AIOT总量: {total0}")
        print(f"USDT总量: {total1}")

    # 获取过去1天的手续费
    fee0, fee1 = get_pool_fees(token0, token1, fee, days=1)
    if fee0 is not None and fee1 is not None:
        print(f"\n过去1天手续费:")
        print(f"AIOT手续费: {fee0}")
        print(f"USDT手续费: {fee1}")
