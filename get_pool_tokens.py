"""
PancakeSwap V3 池子代币数量查询工具

功能说明：
1. 根据两个代币的地址和费率，查询对应的PancakeSwap V3池子
2. 获取池子中两个代币的总量
3. 自动处理代币精度，显示实际数量

使用方法：
1. 确保已安装web3库：pip install web3
2. 修改代码中的token0_address、token1_address和fee参数
3. 运行脚本即可获取池子中的代币数量

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
import json
from decimal import Decimal

# 连接到BSC网络
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed.binance.org/'))

# 加载PancakeV3Pool ABI
with open('ABI/PancakeV3Pool.json', 'r') as f:
    pool_abi = json.load(f)

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
    """
    获取PancakeSwap V3池子中的代币总量

    参数:
    token0_address: token0的合约地址
    token1_address: token1的合约地址
    fee: 费率（例如：3000表示0.3%）

    返回:
    token0_amount: token0的总量
    token1_amount: token1的总量
    """
    # 获取池子合约地址
    factory_address = '0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865'  # PancakeSwap V3 Factory地址
    factory_abi = json.load(open('ABI/PancakeV3Factory.json', 'r'))
    factory_contract = w3.eth.contract(address=Web3.to_checksum_address(factory_address), abi=factory_abi)

    # 获取池子地址
    pool_address = factory_contract.functions.getPool(
        Web3.to_checksum_address(token0_address),
        Web3.to_checksum_address(token1_address),
        fee
    ).call()

    if pool_address == '0x0000000000000000000000000000000000000000':
        print("未找到对应的池子")
        return None, None

    # 创建池子合约实例
    pool_contract = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=pool_abi)

    # 创建代币合约实例
    token0_contract = w3.eth.contract(address=Web3.to_checksum_address(token0_address), abi=ERC20_ABI)
    token1_contract = w3.eth.contract(address=Web3.to_checksum_address(token1_address), abi=ERC20_ABI)

    # 获取代币精度
    token0_decimals = token0_contract.functions.decimals().call()
    token1_decimals = token1_contract.functions.decimals().call()

    # 获取池子中的代币余额
    token0_balance = token0_contract.functions.balanceOf(pool_address).call()
    token1_balance = token1_contract.functions.balanceOf(pool_address).call()

    return token0_balance, token1_balance, token0_decimals, token1_decimals

# 使用示例
if __name__ == "__main__":
    # AIOT-USDT池子
    token0 = "0x55ad16Bd573B3365f43A9dAeB0Cc66A73821b4a5"  # AIOT
    token1 = "0x55d398326f99059fF775485246999027B3197955"  # USDT
    fee = 500  # 0.05%

    token0_amount, token1_amount, token0_decimals, token1_decimals = get_pool_tokens(token0, token1, fee)

    if token0_amount is not None and token1_amount is not None:
        print(f"AIOT总量: {token0_amount / (10 ** token0_decimals)}")
        print(f"USDT总量: {token1_amount / (10 ** token1_decimals)}")
