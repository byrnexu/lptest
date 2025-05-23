import json
from web3 import Web3
from decimal import Decimal
import math

# BSC节点URL
BSC_NODE_URL = "https://bsc-dataseed.binance.org/"

# PancakeSwap V3 Factory合约地址
PANCAKESWAP_V3_FACTORY = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

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
            
        # 创建代币合约实例
        token_contract = w3.eth.contract(abi=ERC20_ABI)
        
        result = {}
        for token_name in token_names:
            try:
                # 获取代币地址
                token_address = get_token_address(token_name)
                
                # 获取代币精度
                decimals = get_token_decimals(token_address, w3)
                
                # 获取代币余额
                balance = token_contract.functions.balanceOf(
                    Web3.to_checksum_address(address)
                ).call(address=Web3.to_checksum_address(token_address))
                
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

if __name__ == "__main__":
    # 示例1：获取AIOT/USDT 0.05%费率池子的价格
    pool_address, price = get_v3_pool_price("AIOT", "USDT", 0.05)
    if pool_address and price:
        print(f"AIOT/USDT V3池子地址: {pool_address}")
        print(f"AIOT/USDT V3池子当前价格: {price:.8f} USDT")
        
    # 示例2：获取指定地址上AIOT和USDT的余额
    wallet_address = "0x55ad16Bd573B3365f43A9dAeB0Cc66A73821b4a5"  # 示例地址
    balances = get_token_balances(wallet_address, ["AIOT", "USDT"])
    
    print("\n代币余额:")
    for token_name, info in balances.items():
        print(f"{token_name}:")
        print(f"  合约地址: {info['address']}")
        print(f"  余额: {info['balance']:.8f}")
        print(f"  精度: {info['decimals']}") 