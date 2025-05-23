import json
from web3 import Web3
from decimal import Decimal
import math
from datetime import datetime, timedelta

# BSC节点URL
BSC_NODE_URL = "https://bsc-dataseed.binance.org/"

# PancakeSwap V3 Factory合约地址
PANCAKESWAP_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

# NonfungiblePositionManager合约地址
POSITION_MANAGER = "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364"

# 加载代币信息
with open("bsc_tokens.json", "r") as f:
    TOKENS = json.load(f)

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
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

def get_token_address(token_identifier: str) -> str:
    """根据代币名称或符号获取地址"""
    for addr, info in TOKENS.items():
        if (info["name"].lower() == token_identifier.lower() or
            info["symbol"].lower() == token_identifier.lower()):
            return addr
    raise ValueError(f"未找到代币: {token_identifier}")

def get_token_decimals(token_address: str, w3: Web3) -> int:
    """获取代币精度"""
    try:
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        return token_contract.functions.decimals().call()
    except Exception as e:
        print(f"获取代币精度时出错: {str(e)}")
        return 18  # 默认精度

def get_v3_pool_price(token0_name: str, token1_name: str, fee_percent: float):
    """获取V3池子的当前价格和地址

    Args:
        token0_name: 第一个代币的名称或符号
        token1_name: 第二个代币的名称或符号
        fee_percent: 费率百分比（例如：0.05表示0.05%）

    Returns:
        tuple: (pool_address, price) 如果找到池子，否则返回 (None, None)
        - pool_address: 池子合约地址
        - price: 代币1/代币0的价格
    """
    try:
        # 初始化Web3
        w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

        # 获取代币地址
        token0_address = get_token_address(token0_name)
        token1_address = get_token_address(token1_name)

        # 加载Factory ABI
        with open("ABI/PancakeV3Factory.json", "r") as f:
            FACTORY_ABI = json.load(f)

        # 加载Pool ABI
        with open("ABI/PancakeV3Pool.json", "r") as f:
            POOL_ABI = json.load(f)

        # 创建Factory合约实例
        factory = w3.eth.contract(address=Web3.to_checksum_address(PANCAKESWAP_V3_FACTORY), abi=FACTORY_ABI)

        # 将费率百分比转换为合约使用的格式
        fee = int(fee_percent * 10000)  # 例如：0.05% -> 500

        # 获取池子地址
        pool_address = factory.functions.getPool(
            Web3.to_checksum_address(token0_address),
            Web3.to_checksum_address(token1_address),
            fee
        ).call()

        if pool_address == "0x0000000000000000000000000000000000000000":
            print(f"未找到{token0_name}/{token1_name} V3池子 (费率: {fee_percent}%)")
            return None, None

        # 创建池子合约实例
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)

        # 获取当前价格信息
        slot0 = pool.functions.slot0().call()
        sqrt_price_x96 = slot0[0]

        # 计算实际价格
        price = (Decimal(sqrt_price_x96) ** 2) / (Decimal(2) ** 192)

        # 获取代币精度
        token0_decimals = get_token_decimals(token0_address, w3)
        token1_decimals = get_token_decimals(token1_address, w3)

        # 调整价格以考虑代币精度差异
        price_adjusted = float(price) * (10 ** (token1_decimals - token0_decimals))

        return pool_address, price_adjusted

    except Exception as e:
        print(f"获取价格时出错: {str(e)}")
        return None, None

def get_token_balances(address: str, token_names: list) -> dict:
    """获取指定地址上多个代币的余额

    Args:
        address: 要查询的钱包地址
        token_names: 代币名称或符号列表

    Returns:
        dict: {
            'token_name': {
                'address': '代币合约地址',
                'balance': '代币余额',
                'decimals': '代币精度'
            },
            ...
        }
    """
    try:
        # 初始化Web3
        w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

        # 检查地址格式
        if not w3.is_address(address):
            raise ValueError(f"无效的地址格式: {address}")

        result = {}
        for token_name in token_names:
            try:
                # 获取代币地址
                token_address = get_token_address(token_name)

                # 创建代币合约实例
                token_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_ABI
                )

                # 获取代币精度
                decimals = token_contract.functions.decimals().call()

                # 获取代币余额
                balance = token_contract.functions.balanceOf(
                    Web3.to_checksum_address(address)
                ).call()

                # 格式化余额
                formatted_balance = float(balance) / (10 ** decimals)

                result[token_name] = {
                    'address': token_address,
                    'balance': formatted_balance,
                    'decimals': decimals
                }

            except Exception as e:
                print(f"获取{token_name}余额时出错: {str(e)}")
                continue

        return result

    except Exception as e:
        print(f"获取代币余额时出错: {str(e)}")
        return {}

def price_to_tick(price: float, token0_decimals: int, token1_decimals: int) -> int:
    """将价格转换为tick

    Args:
        price: 代币1/代币0的价格
        token0_decimals: 代币0的精度
        token1_decimals: 代币1的精度

    Returns:
        int: tick值
    """
    # 调整价格以考虑代币精度差异
    adjusted_price = price * (10 ** (token0_decimals - token1_decimals))
    # 计算tick
    tick = math.log(adjusted_price, 1.0001)
    return int(tick)

def tick_to_price(tick: int, token0_decimals: int, token1_decimals: int) -> float:
    """将tick转换为价格

    Args:
        tick: tick值
        token0_decimals: 代币0的精度
        token1_decimals: 代币1的精度

    Returns:
        float: 代币1/代币0的价格
    """
    # 计算价格
    price = 1.0001 ** tick
    # 调整价格以考虑代币精度差异
    adjusted_price = price / (10 ** (token0_decimals - token1_decimals))
    return adjusted_price

def mint_v3_position(
    token0_name: str,
    token1_name: str,
    fee_percent: float,
    amount0_desired: float,
    amount1_desired: float,
    recipient: str,
    price_range_percent: float = 10.0,
    slippage_percent: float = 1.0,
    deadline_minutes: int = 20
) -> dict:
    """在V3池子中创建流动性

    Args:
        token0_name: 第一个代币的名称或符号
        token1_name: 第二个代币的名称或符号
        fee_percent: 费率百分比（例如：0.05表示0.05%）
        amount0_desired: 期望投入的代币0数量
        amount1_desired: 期望投入的代币1数量
        recipient: 接收NFT的钱包地址
        price_range_percent: 价格范围百分比（例如：10表示上下浮动10%）
        slippage_percent: 滑点百分比（例如：1表示1%）
        deadline_minutes: 交易截止时间（分钟）

    Returns:
        dict: 交易结果
    """
    try:
        # 初始化Web3
        w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

        # 获取代币地址和精度
        token0_address = get_token_address(token0_name)
        token1_address = get_token_address(token1_name)

        # 创建代币合约实例
        token0_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token0_address),
            abi=ERC20_ABI
        )
        token1_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token1_address),
            abi=ERC20_ABI
        )

        # 获取代币精度
        token0_decimals = token0_contract.functions.decimals().call()
        token1_decimals = token1_contract.functions.decimals().call()

        # 获取当前价格
        pool_address, current_price = get_v3_pool_price(token0_name, token1_name, fee_percent)
        if not pool_address or not current_price:
            raise ValueError(f"无法获取{token0_name}/{token1_name}池子价格")

        # 计算价格范围
        price_lower = current_price * (1 - price_range_percent / 100)
        price_upper = current_price * (1 + price_range_percent / 100)

        # 转换为tick
        tick_lower = price_to_tick(price_lower, token0_decimals, token1_decimals)
        tick_upper = price_to_tick(price_upper, token0_decimals, token1_decimals)

        # 计算最小数量（考虑滑点）
        amount0_min = int(amount0_desired * (1 - slippage_percent / 100) * (10 ** token0_decimals))
        amount1_min = int(amount1_desired * (1 - slippage_percent / 100) * (10 ** token1_decimals))

        # 转换期望数量为wei
        amount0_desired_wei = int(amount0_desired * (10 ** token0_decimals))
        amount1_desired_wei = int(amount1_desired * (10 ** token1_decimals))

        # 计算deadline
        deadline = int((datetime.now() + timedelta(minutes=deadline_minutes)).timestamp())

        # 加载PositionManager ABI
        with open("ABI/NonfungiblePositionManager.json", "r") as f:
            POSITION_MANAGER_ABI = json.load(f)

        # 创建PositionManager合约实例
        position_manager = w3.eth.contract(
            address=Web3.to_checksum_address(POSITION_MANAGER),
            abi=POSITION_MANAGER_ABI
        )

        # 准备mint参数
        mint_params = {
            'token0': Web3.to_checksum_address(token0_address),
            'token1': Web3.to_checksum_address(token1_address),
            'fee': int(fee_percent * 10000),  # 转换为合约使用的格式
            'tickLower': tick_lower,
            'tickUpper': tick_upper,
            'amount0Desired': amount0_desired_wei,
            'amount1Desired': amount1_desired_wei,
            'amount0Min': amount0_min,
            'amount1Min': amount1_min,
            'recipient': Web3.to_checksum_address(recipient),
            'deadline': deadline
        }

        # 调用mint函数
        print("创建流动性池子...")
        print("注意: V3使用回调机制处理代币转账，不需要预先授权")
        print("当合约调用pancakeV3MintCallback时，会自动处理代币转账")
        tx = position_manager.functions.mint(mint_params).call()

        return {
            'transaction': tx,
            'pool_address': pool_address,
            'current_price': current_price,
            'price_range': {
                'lower': price_lower,
                'upper': price_upper
            },
            'tick_range': {
                'lower': tick_lower,
                'upper': tick_upper
            },
            'amounts': {
                'token0': {
                    'desired': amount0_desired,
                    'min': amount0_min / (10 ** token0_decimals)
                },
                'token1': {
                    'desired': amount1_desired,
                    'min': amount1_min / (10 ** token1_decimals)
                }
            }
        }

    except Exception as e:
        print(f"创建流动性池子时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 示例1：获取AIOT/USDT 0.05%费率池子的价格
    fee_percent = 0.05
    pool_address, price = get_v3_pool_price("AIOT", "USDT", fee_percent)
    if pool_address and price:
        print(f"AIOT/USDT V3池子地址: {pool_address}")
        print(f"AIOT/USDT V3池子费率: {fee_percent}%")
        print(f"AIOT/USDT V3池子当前价格: {price:.8f} USDT")

    # 示例2：获取指定地址上AIOT和USDT的余额
    wallet_address = "0x33723ef67C37F76B990b583812891c93C2Dbe87C"  # 示例地址
    balances = get_token_balances(wallet_address, ["AIOT", "USDT"])

    print("\n代币余额:")
    for token_name, info in balances.items():
        print(f"{token_name}:")
        print(f"  合约地址: {info['address']}")
        print(f"  余额: {info['balance']:.8f}")
        print(f"  精度: {info['decimals']}")

    # 示例3：创建流动性池子
    print("\n创建流动性池子:")
    result = mint_v3_position(
        token0_name="AIOT",
        token1_name="USDT",
        fee_percent=0.05,
        amount0_desired=1000.0,  # 1000 AIOT
        amount1_desired=360.0,   # 360 USDT
        recipient=wallet_address,
        price_range_percent=10.0,
        slippage_percent=1.0,
        deadline_minutes=20
    )

    if result:
        print("\n交易详情:")
        print(f"池子地址: {result['pool_address']}")
        print(f"当前价格: {result['current_price']:.8f} USDT")
        print(f"价格范围: {result['price_range']['lower']:.8f} - {result['price_range']['upper']:.8f} USDT")
        print(f"Tick范围: {result['tick_range']['lower']} - {result['tick_range']['upper']}")
        print(f"AIOT数量: {result['amounts']['token0']['desired']:.2f} (最小: {result['amounts']['token0']['min']:.2f})")
        print(f"USDT数量: {result['amounts']['token1']['desired']:.2f} (最小: {result['amounts']['token1']['min']:.2f})")
