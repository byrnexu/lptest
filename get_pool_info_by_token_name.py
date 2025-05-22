from web3 import Web3
import json
from decimal import Decimal
import sys
import signal
import time

# BSC RPC节点
BSC_RPC = "https://bsc-dataseed.binance.org/"

# PancakeSwap V3 Factory 合约地址
FACTORY_ADDRESS = "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865"

# 支持的费率等级 (从0.01%到3%，步长0.01%)
FEE_TIERS = [int(fee * 100) for fee in range(1, 101)]  # 1-300 对应 0.01%-3%

# 全局变量用于控制程序退出
should_exit = False

def signal_handler(signum, frame):
    """处理Ctrl+C信号"""
    global should_exit
    print("\n\n正在优雅退出...")
    should_exit = True

def load_abi(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def load_tokens():
    """加载代币信息"""
    with open('bsc_tokens.json', 'r') as f:
        return json.load(f)

def get_token_address_by_name_or_symbol(token_input, tokens_data):
    """根据代币名称或符号获取地址，如果有多个匹配，返回rank最小的"""
    matching_tokens = []
    for address, token_info in tokens_data.items():
        if (token_info['name'].lower() == token_input.lower() or 
            token_info['symbol'].lower() == token_input.lower()):
            matching_tokens.append((token_info['rank'], address, token_info['name'], token_info['symbol']))
    
    if not matching_tokens:
        return None, None, None
    
    # 按rank排序，返回rank最小的代币信息
    matching_tokens.sort()  # 默认升序排序，rank最小的在前面
    rank, address, name, symbol = matching_tokens[0]
    return address, name, symbol

def get_pool_info(w3, factory_contract, token0_address, token1_address, fee, token0_symbol, token1_symbol):
    """获取特定费率下的池子信息"""
    try:
        pool_address = factory_contract.functions.getPool(token0_address, token1_address, fee).call()
        if pool_address == "0x0000000000000000000000000000000000000000":
            return None
        
        # 加载池子合约的ABI（这里使用最小ABI，只包含我们需要的方法）
        pool_abi = json.loads('''[
            {"inputs":[],"name":"token0","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"token1","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"slot0","outputs":[{"internalType":"uint160","name":"sqrtPriceX96","type":"uint160"},{"internalType":"int24","name":"tick","type":"int24"},{"internalType":"uint16","name":"observationIndex","type":"uint16"},{"internalType":"uint16","name":"observationCardinality","type":"uint16"},{"internalType":"uint16","name":"observationCardinalityNext","type":"uint16"},{"internalType":"uint8","name":"feeProtocol","type":"uint8"},{"internalType":"bool","name":"unlocked","type":"bool"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"liquidity","outputs":[{"internalType":"uint128","name":"","type":"uint128"}],"stateMutability":"view","type":"function"}
        ]''')
        
        # 加载ERC20代币ABI
        erc20_abi = json.loads('''[
            {"inputs":[],"name":"decimals","outputs":[{"internalType":"uint8","name":"","type":"uint8"}],"stateMutability":"view","type":"function"},
            {"inputs":[],"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}
        ]''')
        
        pool_contract = w3.eth.contract(address=pool_address, abi=pool_abi)
        token0_contract = w3.eth.contract(address=token0_address, abi=erc20_abi)
        token1_contract = w3.eth.contract(address=token1_address, abi=erc20_abi)
        
        try:
            # 获取池子基本信息
            slot0 = pool_contract.functions.slot0().call()
            liquidity = pool_contract.functions.liquidity().call()
            
            # 获取代币精度
            token0_decimals = token0_contract.functions.decimals().call()
            token1_decimals = token1_contract.functions.decimals().call()
            
            # 获取池子中的代币余额
            token0_balance = token0_contract.functions.balanceOf(pool_address).call()
            token1_balance = token1_contract.functions.balanceOf(pool_address).call()
            
            # 计算当前价格
            sqrt_price_x96 = slot0[0]
            price = (sqrt_price_x96 * sqrt_price_x96 * (10 ** 18)) // (1 << 192)
            
            return {
                "pool_address": pool_address,
                "fee": fee,
                "current_price": price,
                "current_tick": slot0[1],
                "liquidity": liquidity,
                "token0_balance": token0_balance,
                "token1_balance": token1_balance,
                "token0_decimals": token0_decimals,
                "token1_decimals": token1_decimals,
                "token0_symbol": token0_symbol,
                "token1_symbol": token1_symbol
            }
        except Exception as e:
            # 如果标准调用失败，尝试使用raw_call
            try:
                # 使用raw_call获取slot0数据
                slot0_data = w3.eth.call({
                    'to': pool_address,
                    'data': '0x3850c7bd'  # slot0() 函数的签名
                })
                
                # 手动解码返回值
                slot0_data = slot0_data[32:]
                sqrt_price_x96 = int.from_bytes(slot0_data[:32], 'big')
                tick = int.from_bytes(slot0_data[32:64], 'big', signed=True)
                
                # 获取liquidity数据
                liquidity_data = w3.eth.call({
                    'to': pool_address,
                    'data': '0x1a686502'  # liquidity() 函数的签名
                })
                liquidity = int.from_bytes(liquidity_data[32:], 'big')
                
                # 获取代币精度
                token0_decimals_data = w3.eth.call({
                    'to': token0_address,
                    'data': '0x313ce567'  # decimals() 函数的签名
                })
                token1_decimals_data = w3.eth.call({
                    'to': token1_address,
                    'data': '0x313ce567'  # decimals() 函数的签名
                })
                token0_decimals = int.from_bytes(token0_decimals_data[32:], 'big')
                token1_decimals = int.from_bytes(token1_decimals_data[32:], 'big')
                
                # 获取代币余额
                token0_balance_data = w3.eth.call({
                    'to': token0_address,
                    'data': '0x70a08231000000000000000000000000' + pool_address[2:]  # balanceOf(address) 函数的签名
                })
                token1_balance_data = w3.eth.call({
                    'to': token1_address,
                    'data': '0x70a08231000000000000000000000000' + pool_address[2:]  # balanceOf(address) 函数的签名
                })
                token0_balance = int.from_bytes(token0_balance_data[32:], 'big')
                token1_balance = int.from_bytes(token1_balance_data[32:], 'big')
                
                # 计算当前价格
                price = (sqrt_price_x96 * sqrt_price_x96 * (10 ** 18)) // (1 << 192)
                
                return {
                    "pool_address": pool_address,
                    "fee": fee,
                    "current_price": price,
                    "current_tick": tick,
                    "liquidity": liquidity,
                    "token0_balance": token0_balance,
                    "token1_balance": token1_balance,
                    "token0_decimals": token0_decimals,
                    "token1_decimals": token1_decimals,
                    "token0_symbol": token0_symbol,
                    "token1_symbol": token1_symbol
                }
            except Exception as e2:
                print(f"\n获取池子 {pool_address} 信息时出错: {str(e2)}")
                return None
                
    except Exception as e:
        print(f"\n获取池子信息时出错: {str(e)}")
        return None

def format_token_amount(amount, decimals):
    """格式化代币数量，使其更易读"""
    amount_decimal = Decimal(amount) / Decimal(10 ** decimals)
    if amount_decimal >= 1000000:
        return f"{amount_decimal:,.2f}"
    elif amount_decimal >= 1000:
        return f"{amount_decimal:,.4f}"
    else:
        return f"{amount_decimal:,.8f}"

def print_progress(current, total, start_time):
    """打印进度条"""
    progress = current / total * 100
    elapsed_time = time.time() - start_time
    estimated_total = elapsed_time / (current / total) if current > 0 else 0
    remaining_time = estimated_total - elapsed_time
    
    # 创建进度条
    bar_length = 30
    filled_length = int(bar_length * current / total)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    
    # 打印进度信息
    sys.stdout.write(f'\r进度: [{bar}] {progress:.1f}% ({current}/{total}) | 已用时间: {elapsed_time:.1f}s | 预计剩余时间: {remaining_time:.1f}s')
    sys.stdout.flush()

def main():
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    
    # 创建Web3实例
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))
    
    # 检查连接
    if not w3.is_connected():
        print("无法连接到BSC网络")
        return
    
    # 加载代币数据
    tokens_data = load_tokens()
    
    # 加载Factory合约ABI
    factory_abi = load_abi("ABI/PancakeV3Factory.ABI")
    factory_contract = w3.eth.contract(address=FACTORY_ADDRESS, abi=factory_abi)
    
    # 获取用户输入的代币名称或符号
    token0_input = input("请输入第一个代币名称或符号: ").strip()
    token1_input = input("请输入第二个代币名称或符号: ").strip()
    
    # 获取代币地址和信息
    token0_address, token0_name, token0_symbol = get_token_address_by_name_or_symbol(token0_input, tokens_data)
    token1_address, token1_name, token1_symbol = get_token_address_by_name_or_symbol(token1_input, tokens_data)
    
    if not token0_address or not token1_address:
        print("未找到指定的代币，请检查代币名称或符号是否正确")
        return
    
    print(f"\n正在查询 {token0_name} ({token0_symbol}) 和 {token1_name} ({token1_symbol}) 的池子信息...")
    print(f"代币地址: {token0_address} 和 {token1_address}\n")
    
    # 存储存在的池子信息
    existing_pools = []
    
    # 记录开始时间
    start_time = time.time()
    
    # 查询所有费率等级的池子
    total_fees = len(FEE_TIERS)
    for i, fee in enumerate(FEE_TIERS, 1):
        if should_exit:
            break
            
        pool_info = get_pool_info(w3, factory_contract, token0_address, token1_address, fee, token0_symbol, token1_symbol)
        if pool_info:
            existing_pools.append(pool_info)
        
        # 打印进度
        print_progress(i, total_fees, start_time)
    
    # 打印最终的换行
    print("\n")
    
    # 打印存在的池子信息
    if existing_pools:
        print(f"\n找到 {len(existing_pools)} 个存在的池子:")
        for pool in existing_pools:
            print(f"\n费率 {pool['fee']/10000}% 的池子信息:")
            print(f"池子地址: {pool['pool_address']}")
            print(f"当前价格: {pool['current_price']}")
            print(f"当前Tick: {pool['current_tick']}")
            print(f"流动性: {pool['liquidity']}")
            print(f"代币数量:")
            print(f"  {pool['token0_symbol']}: {format_token_amount(pool['token0_balance'], pool['token0_decimals'])}")
            print(f"  {pool['token1_symbol']}: {format_token_amount(pool['token1_balance'], pool['token1_decimals'])}")
            print("-" * 50)
    else:
        print("\n未找到任何存在的池子")

if __name__ == "__main__":
    main() 