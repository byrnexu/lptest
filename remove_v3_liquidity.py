from web3 import Web3
from eth_abi import encode
import json
import math
from decimal import Decimal
from dotenv import load_dotenv
import os
import sys
from web3.middleware import geth_poa_middleware

# 加载.env文件
load_dotenv()

# 从.env文件获取私钥和RPC URL
PRIVATE_KEY = os.getenv('PRIVATE_KEY')
RPC_URL = os.getenv('RPC_URL')

if not PRIVATE_KEY:
    raise ValueError("请在.env文件中设置PRIVATE_KEY")
if not RPC_URL:
    raise ValueError("请在.env文件中设置RPC_URL")

# 检查命令行参数
if len(sys.argv) != 2:
    print("使用方法: python remove_v3_liquidity.py <token_id>")
    sys.exit(1)

try:
    token_id = int(sys.argv[1])
except ValueError:
    print("错误: token_id必须是整数")
    sys.exit(1)

# 连接到以太坊网络
w3 = Web3(Web3.HTTPProvider(RPC_URL))
# 添加POA中间件
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

if not w3.is_connected():
    raise ValueError("无法连接到以太坊网络，请检查RPC URL是否正确")

# 获取网络信息
chain_id = w3.eth.chain_id
print(f"当前网络Chain ID: {chain_id}")

# 验证是否在BSC网络上
if chain_id != 56:  # BSC主网的chain_id是56
    raise ValueError(f"当前网络Chain ID为{chain_id}，不是BSC主网(56)")

# Position Manager合约地址
POSITION_MANAGER_ADDRESS = '0x46A15B0b27311cedF172AB29E4f4766fbE7F4364'
print(f"Position Manager地址: {POSITION_MANAGER_ADDRESS}")

# 验证合约地址
if not w3.eth.get_code(POSITION_MANAGER_ADDRESS):
    raise ValueError("合约地址无效或合约未部署")

# 接收钱包地址
RECIPIENT_ADDRESS = '0x33723ef67C37F76B990b583812891c93C2Dbe87C'

# 从文件加载ABI
try:
    with open('ABI/NonfungiblePositionManager.json', 'r') as f:
        POSITION_MANAGER_ABI = json.load(f)
except FileNotFoundError:
    raise ValueError("找不到ABI文件: ABI/NonfungiblePositionManager.json")
except json.JSONDecodeError:
    raise ValueError("ABI文件格式错误")

def get_token_decimals(token_address):
    # 获取代币精度
    token_abi = [
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "type": "function"
        }
    ]
    token_contract = w3.eth.contract(address=token_address, abi=token_abi)
    return token_contract.functions.decimals().call()

def format_amount(amount, decimals):
    return Decimal(amount) / Decimal(10 ** decimals)

def format_bnb_amount(wei_amount):
    return Decimal(wei_amount) / Decimal(10 ** 18)

def remove_liquidity(token_id):
    try:
        # 创建Position Manager合约实例
        position_manager = w3.eth.contract(
            address=POSITION_MANAGER_ADDRESS,
            abi=POSITION_MANAGER_ABI
        )

        # 1. 获取position信息
        print("\n1. 获取Position信息...")
        try:
            position = position_manager.functions.positions(token_id).call()
            print("\nPosition详细信息:")
            print(f"Nonce: {position[0]}")
            print(f"Operator: {position[1]}")
            print(f"Token0: {position[2]}")
            print(f"Token1: {position[3]}")
            print(f"Fee: {position[4]}")
            print(f"TickLower: {position[5]}")
            print(f"TickUpper: {position[6]}")
            print(f"流动性数量: {position[7]}")
            print(f"FeeGrowthInside0LastX128: {position[8]}")
            print(f"FeeGrowthInside1LastX128: {position[9]}")
            print(f"已累积的Token0费用: {position[10]}")
            print(f"已累积的Token1费用: {position[11]}")

            # 获取代币精度
            token0_decimals = get_token_decimals(position[2])
            token1_decimals = get_token_decimals(position[3])

            print("\n格式化后的费用信息:")
            print(f"Token0 费用: {format_amount(position[10], token0_decimals):.12f}")
            print(f"Token1 费用: {format_amount(position[11], token1_decimals):.12f}")

            # 验证position是否属于当前钱包
            if position[1].lower() != RECIPIENT_ADDRESS.lower():
                print(f"\n警告: 该position的operator ({position[1]}) 不是当前钱包地址 ({RECIPIENT_ADDRESS})")
                if input("是否继续? (y/n): ").lower() != 'y':
                    sys.exit(1)

        except Exception as e:
            print(f"获取Position信息失败: {str(e)}")
            print("请确认:")
            print("1. token_id是否正确")
            print("2. 是否在正确的网络上")
            print("3. 该token_id是否属于你的钱包")
            raise

        # 获取当前nonce
        current_nonce = w3.eth.get_transaction_count(RECIPIENT_ADDRESS)

        # 2. 移除流动性（如果流动性不为0）
        if position[7] > 0:
            print("\n2. 移除流动性...")
            deadline = w3.eth.get_block('latest').timestamp + 3600  # 1小时后过期
            
            # 计算最小接收数量（99%）
            amount0_min = int(position[10] * 0.99)
            amount1_min = int(position[11] * 0.99)

            # 创建DecreaseLiquidityParams结构体
            decrease_params = {
                'tokenId': token_id,
                'liquidity': position[7],  # 全部流动性
                'amount0Min': amount0_min,
                'amount1Min': amount1_min,
                'deadline': deadline
            }

            decrease_tx = position_manager.functions.decreaseLiquidity(decrease_params).build_transaction({
                'from': RECIPIENT_ADDRESS,
                'gas': 500000,
                'gasPrice': w3.eth.gas_price,
                'nonce': current_nonce,
            })

            # 发送交易
            signed_tx = w3.eth.account.sign_transaction(decrease_tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
            
            # 计算消耗的BNB
            gas_used = tx_receipt['gasUsed']
            gas_price = decrease_tx['gasPrice']
            bnb_cost = gas_used * gas_price
            
            print(f"移除流动性交易哈希: {tx_hash.hex()}")
            print(f"Gas消耗: {gas_used}")
            print(f"Gas价格: {gas_price} wei")
            print(f"BNB消耗: {format_bnb_amount(bnb_cost):.8f} BNB")
            
            # 更新nonce
            current_nonce += 1
        else:
            print("\n2. 跳过移除流动性步骤（流动性为0）")

        # 3. 收集代币
        print("\n3. 收集代币...")
        # 创建CollectParams结构体
        collect_params = {
            'tokenId': token_id,
            'recipient': RECIPIENT_ADDRESS,
            'amount0Max': 2**128 - 1,  # uint128.max
            'amount1Max': 2**128 - 1   # uint128.max
        }

        collect_tx = position_manager.functions.collect(collect_params).build_transaction({
            'from': RECIPIENT_ADDRESS,
            'gas': 500000,
            'gasPrice': w3.eth.gas_price,
            'nonce': current_nonce,
        })

        # 发送交易
        signed_tx = w3.eth.account.sign_transaction(collect_tx, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        # 计算消耗的BNB
        gas_used = tx_receipt['gasUsed']
        gas_price = collect_tx['gasPrice']
        bnb_cost = gas_used * gas_price
        
        print(f"收集代币交易哈希: {tx_hash.hex()}")
        print(f"Gas消耗: {gas_used}")
        print(f"Gas价格: {gas_price} wei")
        print(f"BNB消耗: {format_bnb_amount(bnb_cost):.8f} BNB")

        # 直接从交易收据中获取收集的代币数量
        amount0_collected = 0
        amount1_collected = 0
        
        # 遍历所有日志
        for log in tx_receipt['logs']:
            try:
                # 尝试解析日志
                parsed_log = position_manager.events.Collect().process_log(log)
                amount0_collected = parsed_log['args']['amount0']
                amount1_collected = parsed_log['args']['amount1']
                break
            except Exception:
                continue

        # 如果无法从事件中获取，则使用position中的费用信息
        if amount0_collected == 0 and amount1_collected == 0:
            amount0_collected = position[10]
            amount1_collected = position[11]

        print("\n最终结果:")
        print(f"Token0 收集数量: {format_amount(amount0_collected, token0_decimals):.12f}")
        print(f"Token1 收集数量: {format_amount(amount1_collected, token1_decimals):.12f}")
        print(f"Token0 手续费: {format_amount(position[10], token0_decimals):.12f}")
        print(f"Token1 手续费: {format_amount(position[11], token1_decimals):.12f}")

    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        raise

if __name__ == "__main__":
    remove_liquidity(token_id) 