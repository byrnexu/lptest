import json
from web3 import Web3
from decimal import Decimal
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

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

def calculate_price(sqrt_price_x96, token0_decimals, token1_decimals):
    """计算价格，保持Decimal精度

    Args:
        sqrt_price_x96: 价格的平方根（Q96.96格式）
        token0_decimals: 代币0的精度
        token1_decimals: 代币1的精度

    Returns:
        Decimal: 调整后的价格（保持Decimal精度）
    """
    # 计算基础价格 (token1相对于token0的价格)
    price = (Decimal(sqrt_price_x96) ** 2) / (Decimal(2) ** 192)

    # 调整decimal差异
    price_adjusted = price * (10 ** token0_decimals) / (10 ** token1_decimals)

    return price_adjusted  # 返回Decimal，不转换为float

def get_v3_pool_price(token0_name: str, token1_name: str, fee_percent: float):
    """获取V3池子的当前价格和地址

    Args:
        token0_name: 第一个代币的名称或符号
        token1_name: 第二个代币的名称或符号
        fee_percent: 费率百分比（例如：0.05表示0.05%）

    Returns:
        tuple: (pool_address, price, is_initialized, token0_name, token1_name, sqrt_price_x96, tick) 如果找到池子，否则返回 (None, None, False, None, None, None, None)
        - pool_address: 池子合约地址
        - price: 代币1/代币0的价格（Decimal类型）
        - is_initialized: 池子是否已初始化
        - token0_name: 排序后的token0名称
        - token1_name: 排序后的token1名称
        - sqrt_price_x96: 当前价格的平方根（Q96.96格式）
        - tick: 当前价格对应的tick值
    """
    try:
        # 初始化Web3
        w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

        # 获取代币地址
        token0_address = get_token_address(token0_name)
        token1_address = get_token_address(token1_name)

        # 确保代币地址按字典序排序
        if int(token0_address, 16) > int(token1_address, 16):
            token0_address, token1_address = token1_address, token0_address
            token0_name, token1_name = token1_name, token0_name

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
            return None, None, False, None, None, None, None

        # 创建池子合约实例
        pool = w3.eth.contract(address=Web3.to_checksum_address(pool_address), abi=POOL_ABI)

        try:
            # 获取当前价格信息
            slot0 = pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            tick = slot0[1]  # 获取当前tick

            # 检查池子是否已初始化
            if sqrt_price_x96 == 0:
                print(f"池子尚未初始化")
                return pool_address, None, False, token0_name, token1_name, None, None

            # 获取代币精度
            token0_decimals = get_token_decimals(token0_address, w3)
            token1_decimals = get_token_decimals(token1_address, w3)

            # 使用新的价格计算方法，保持Decimal精度
            price_adjusted = calculate_price(sqrt_price_x96, token0_decimals, token1_decimals)

            return pool_address, price_adjusted, True, token0_name, token1_name, sqrt_price_x96, tick

        except Exception as e:
            print(f"获取池子信息时出错: {str(e)}")
            return pool_address, None, False, token0_name, token1_name, None, None

    except Exception as e:
        print(f"获取价格时出错: {str(e)}")
        return None, None, False, None, None, None, None

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

def price_to_tick(price: Decimal, token0_decimals: int, token1_decimals: int) -> int:
    """将价格转换为tick

    Args:
        price: 代币1/代币0的价格（Decimal类型）
        token0_decimals: 代币0的精度
        token1_decimals: 代币1的精度

    Returns:
        int: tick值
    """
    from decimal import ROUND_DOWN

    # 调整价格以考虑代币精度差异
    adjusted_price = price * Decimal(10 ** (token0_decimals - token1_decimals))

    # 计算tick，使用Decimal的ln函数
    tick = adjusted_price.ln() / Decimal('1.0001').ln()

    # 向下取整，与合约保持一致
    return int(tick.to_integral_value(rounding=ROUND_DOWN))

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
    private_key: str = None,
    price_range_percent: float = 0.5,
    slippage_percent: float = 5.0,
    deadline_minutes: int = 20,
    send_transaction: bool = False
) -> dict:
    try:
        # 初始化Web3
        w3 = Web3(Web3.HTTPProvider(BSC_NODE_URL))

        # 导入Decimal
        from decimal import Decimal, ROUND_DOWN

        # 获取代币地址和精度
        token0_address = get_token_address(token0_name)
        token1_address = get_token_address(token1_name)

        # 确保代币地址按字典序排序
        if int(token0_address, 16) > int(token1_address, 16):
            token0_address, token1_address = token1_address, token0_address
            token0_name, token1_name = token1_name, token0_name
            amount0_desired, amount1_desired = amount1_desired, amount0_desired

        print(f"\n代币信息:")
        print(f"Token0 ({token0_name}): {token0_address}")
        print(f"Token1 ({token1_name}): {token1_address}")

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

        print(f"\n代币精度:")
        print(f"Token0 ({token0_name}): {token0_decimals}")
        print(f"Token1 ({token1_name}): {token1_decimals}")

        # 获取当前价格
        pool_address, current_price, is_initialized, sorted_token0_name, sorted_token1_name, sqrt_price_x96, tick = get_v3_pool_price(token0_name, token1_name, fee_percent)
        if not pool_address:
            raise ValueError(f"无法获取{token0_name}/{token1_name}池子")

        if not is_initialized:
            raise ValueError(f"池子尚未初始化，需要先初始化池子")

        print(f"\n池子已经初始化，池子信息:")
        print(f"池子地址: {pool_address}")
        print(f"当前价格: {current_price:.8f} {sorted_token1_name}")

        # 直接使用返回的tick计算tick范围
        tick_range = int(abs(tick) * price_range_percent / 100)  # 计算tick范围
        # 对于负tick，我们需要调整计算方式
        if tick < 0:
            tick_lower = tick - tick_range  # 更小的tick值对应更高的价格
            tick_upper = tick + tick_range  # 更大的tick值对应更低的价格
        else:
            tick_lower = tick - tick_range  # 更小的tick值对应更低的价格
            tick_upper = tick + tick_range  # 更大的tick值对应更高的价格

        # 确保tick范围是60的倍数（PancakeSwap V3的要求）
        tick_lower = (tick_lower // 60) * 60
        tick_upper = (tick_upper // 60) * 60

        print(f"\nTick范围:")
        print(f"当前Tick: {tick}")
        print(f"Tick下限: {tick_lower}")
        print(f"Tick上限: {tick_upper}")

        # 确保tick范围有效
        if tick_lower >= tick_upper:
            raise ValueError(f"无效的tick范围: {tick_lower} >= {tick_upper}")

        # 确保tick范围在合约允许的范围内
        MIN_TICK = -887272
        MAX_TICK = 887272
        if tick_lower < MIN_TICK or tick_upper > MAX_TICK:
            raise ValueError(f"tick范围超出限制: {MIN_TICK} <= tick <= {MAX_TICK}")

        # 转换期望数量为wei（使用Decimal确保精度）
        amount0_desired_wei = int(Decimal(str(amount0_desired)) * Decimal(10 ** token0_decimals))
        amount1_desired_wei = int(Decimal(str(amount1_desired)) * Decimal(10 ** token1_decimals))

        # 计算最小数量（考虑滑点，使用Decimal确保精度）
        amount0_min = int(Decimal(str(amount0_desired)) * (Decimal('1') - 10 * Decimal(str(slippage_percent)) / Decimal('100')) * Decimal(10 ** token0_decimals))
        amount1_min = int(Decimal(str(amount1_desired)) * (Decimal('1') - 10 * Decimal(str(slippage_percent)) / Decimal('100')) * Decimal(10 ** token1_decimals))

        print(f"\n数量信息:")
        print(f"Token0 ({token0_name}):")
        print(f"  期望数量: {amount0_desired_wei} (wei)")
        print(f"  最小数量: {amount0_min} (wei)")
        print(f"Token1 ({token1_name}):")
        print(f"  期望数量: {amount1_desired_wei} (wei)")
        print(f"  最小数量: {amount1_min} (wei)")

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
        fee = int(Decimal(str(fee_percent)) * Decimal('10000'))  # 转换为合约使用的格式

        mint_params = {
            'token0': Web3.to_checksum_address(token0_address),
            'token1': Web3.to_checksum_address(token1_address),
            'fee': fee,
            'tickLower': tick_lower,
            'tickUpper': tick_upper,
            'amount0Desired': amount0_desired_wei,
            'amount1Desired': amount1_desired_wei,
            'amount0Min': amount0_min,
            'amount1Min': amount1_min,
            'recipient': Web3.to_checksum_address(recipient),
            'deadline': deadline
        }

        # mint_params = {
        #     'token0': "0x55ad16Bd573B3365f43A9dAeB0Cc66A73821b4a5",
        #     'token1': "0x55d398326f99059fF775485246999027B3197955",
        #     'fee': 500,
        #     'tickLower': -11930,
        #     'tickUpper': -9840,
        #     'amount0Desired': 70039168353970460471,
        #     'amount1Desired': 24182265566658884179,
        #     'amount0Min': 66571207111840214314,
        #     'amount1Min': 23007124485730832111,
        #     'recipient': "0x33723ef67C37F76B990b583812891c93C2Dbe87C",
        #     'deadline': deadline
        # }

        print("\n=== Mint参数详情 ===")
        print(f"Token0: {mint_params['token0']}")
        print(f"Token1: {mint_params['token1']}")
        print(f"Fee: {mint_params['fee']}")
        print(f"Tick范围: {mint_params['tickLower']} - {mint_params['tickUpper']}")
        print(f"Token0期望数量: {mint_params['amount0Desired']} (wei)")
        print(f"Token1期望数量: {mint_params['amount1Desired']} (wei)")
        print(f"Token0最小数量: {mint_params['amount0Min']} (wei)")
        print(f"Token1最小数量: {mint_params['amount1Min']} (wei)")
        print(f"接收地址: {mint_params['recipient']}")
        print(f"截止时间: {datetime.fromtimestamp(mint_params['deadline'])}")

        print("\n=== 价格范围信息 ===")
        print(f"当前价格: {current_price:.8f} {sorted_token1_name}")
        print(f"价格下限: {tick_lower}")
        print(f"价格上限: {tick_upper}")
        print(f"价格范围百分比: {price_range_percent}%")
        print(f"滑点百分比: {slippage_percent}%")

        print("\n=== 代币数量信息 ===")
        print(f"Token0 ({token0_name}):")
        print(f"  原始数量: {amount0_desired}")
        print(f"  转换为wei: {amount0_desired_wei}")
        print(f"  最小数量(wei): {amount0_min}")
        print(f"Token1 ({token1_name}):")
        print(f"  原始数量: {amount1_desired}")
        print(f"  转换为wei: {amount1_desired_wei}")
        print(f"  最小数量(wei): {amount1_min}")

        if send_transaction and private_key:
            # 获取账户地址
            account = w3.eth.account.from_key(private_key)
            address = account.address

            # 获取nonce
            nonce = w3.eth.get_transaction_count(address)

            # 获取gas价格
            gas_price = w3.eth.gas_price

            # 构建交易
            transaction = position_manager.functions.mint(mint_params).build_transaction({
                'from': address,
                'nonce': nonce,
                'gas': 5000000,  # 设置一个足够大的gas限制
                'gasPrice': gas_price,
                'chainId': 56  # BSC主网chainId
            })

            # 签名交易
            signed_txn = w3.eth.account.sign_transaction(transaction, private_key)

            # 发送交易
            print("\n发送交易...")
            try:
                tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

                # 等待交易确认
                print("等待交易确认...")
                tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

                # 检查交易状态
                if tx_receipt.status == 0:
                    print("\n交易失败!")
                    print(f"交易哈希: {tx_hash.hex()}")
                    print(f"区块号: {tx_receipt['blockNumber']}")

                    # 尝试获取失败原因
                    try:
                        tx = w3.eth.get_transaction(tx_hash)
                        result = w3.eth.call(tx, tx_receipt.blockNumber - 1)
                        error_msg = str(result)
                        print(f"交易失败原因: {error_msg}")

                        # 处理 STF 错误
                        if "STF" in error_msg:
                            print("\nSTF (Safe Transfer Failed) 错误可能的原因:")
                            print("1. 代币余额不足")
                            print("2. 代币合约可能暂停了转账功能")
                            print("3. 代币合约可能有其他限制")

                            # 检查余额
                            token0_contract = w3.eth.contract(address=Web3.to_checksum_address(token0_address), abi=ERC20_ABI)
                            token1_contract = w3.eth.contract(address=Web3.to_checksum_address(token1_address), abi=ERC20_ABI)

                            balance0 = token0_contract.functions.balanceOf(
                                Web3.to_checksum_address(recipient)
                            ).call()
                            balance1 = token1_contract.functions.balanceOf(
                                Web3.to_checksum_address(recipient)
                            ).call()

                            print("\n当前余额:")
                            print(f"Token0 ({token0_name}): {balance0 / (10 ** token0_decimals):.8f}")
                            print(f"Token1 ({token1_name}): {balance1 / (10 ** token1_decimals):.8f}")

                            print("\n需要数量:")
                            print(f"Token0 ({token0_name}): {amount0_desired_wei / (10 ** token0_decimals):.8f}")
                            print(f"Token1 ({token1_name}): {amount1_desired_wei / (10 ** token1_decimals):.8f}")

                    except Exception as e:
                        print(f"无法获取详细失败原因: {str(e)}")
                    return None

                # 解析交易日志获取返回值
                # 只处理 IncreaseLiquidity 事件
                increase_liquidity_event = position_manager.events.IncreaseLiquidity()
                logs = []
                for log in tx_receipt['logs']:
                    try:
                        # 检查日志是否来自 PositionManager 合约
                        if log['address'].lower() == POSITION_MANAGER.lower():
                            # 尝试解析事件
                            parsed_log = increase_liquidity_event.process_log(log)
                            if parsed_log:
                                logs.append(parsed_log)
                    except Exception:
                        continue

                if not logs:
                    print("\n警告: 未找到 IncreaseLiquidity 事件")
                    print(f"交易哈希: {tx_hash.hex()}")
                    print(f"区块号: {tx_receipt['blockNumber']}")
                    return None

                log = logs[0]
                tokenId = log['args']['tokenId']
                liquidity = log['args']['liquidity']
                amount0 = log['args']['amount0']
                amount1 = log['args']['amount1']

                print("\n=== Mint函数返回值 ===")
                print(f"Token ID: {tokenId}")
                print(f"流动性数量: {liquidity}")
                print(f"Token0 实际使用数量: {amount0 / (10 ** token0_decimals):.8f}")
                print(f"Token1 实际使用数量: {amount1 / (10 ** token1_decimals):.8f}")
                print(f"交易哈希: {tx_hash.hex()}")
                print(f"区块号: {tx_receipt['blockNumber']}")

            except Exception as e:
                print("\n交易发送失败!")
                print(f"错误类型: {type(e).__name__}")
                print(f"错误信息: {str(e)}")

                # 如果是 gas 相关错误
                if "gas required exceeds allowance" in str(e).lower():
                    print("\nGas 不足，请增加 gas 限制")
                # 如果是余额不足错误
                elif "insufficient funds" in str(e).lower():
                    print("\n余额不足，请检查代币余额")
                # 如果是滑点错误
                elif "slippage" in str(e).lower():
                    print("\n滑点过大，请调整滑点参数")

                return None

            return {
                'transaction_hash': tx_hash.hex(),
                'status': tx_receipt.status,
                'tokenId': tokenId if logs else None,
                'liquidity': liquidity if logs else None,
                'amount0': amount0 if logs else None,
                'amount1': amount1 if logs else None,
                'pool_address': pool_address,
                'current_price': current_price,
                'price_range': {
                    'lower': tick_lower,
                    'upper': tick_upper
                },
                'tick_range': {
                    'lower': tick_lower,
                    'upper': tick_upper
                },
                'amounts': {
                    'token0': {
                        'desired': amount0_desired,
                        'min': amount0_min / (10 ** token0_decimals),
                        'actual': amount0 / (10 ** token0_decimals) if logs else None
                    },
                    'token1': {
                        'desired': amount1_desired,
                        'min': amount1_min / (10 ** token1_decimals),
                        'actual': amount1 / (10 ** token1_decimals) if logs else None
                    }
                }
            }
        else:
            # 模拟调用
            try:
                # 尝试获取更详细的错误信息
                tokenId, liquidity, amount0, amount1 = position_manager.functions.mint(mint_params).call()

                print("\n=== Mint函数返回值 ===")
                print(f"Token ID: {tokenId}")
                print(f"流动性数量: {liquidity}")
                print(f"Token0 实际使用数量: {amount0 / (10 ** token0_decimals):.8f}")
                print(f"Token1 实际使用数量: {amount1 / (10 ** token1_decimals):.8f}")

                return {
                    'tokenId': tokenId,
                    'liquidity': liquidity,
                    'amount0': amount0,
                    'amount1': amount1,
                    'pool_address': pool_address,
                    'current_price': current_price,
                    'price_range': {
                        'lower': tick_lower,
                        'upper': tick_upper
                    },
                    'tick_range': {
                        'lower': tick_lower,
                        'upper': tick_upper
                    },
                    'amounts': {
                        'token0': {
                            'desired': amount0_desired,
                            'min': amount0_min / (10 ** token0_decimals),
                            'actual': amount0 / (10 ** token0_decimals)
                        },
                        'token1': {
                            'desired': amount1_desired,
                            'min': amount1_min / (10 ** token1_decimals),
                            'actual': amount1 / (10 ** token1_decimals)
                        }
                    }
                }
            except Exception as e:
                error_msg = str(e)
                print(f"\n模拟调用失败，详细错误信息:")
                print(f"错误类型: {type(e).__name__}")
                print(f"错误信息: {error_msg}")

                # 检查是否是STF错误
                if "execution reverted: STF" in error_msg:
                    print("\n注意: 在模拟环境中出现STF错误，这通常是由于模拟环境的限制导致的。")
                    print("在生产环境中，这个交易可能会成功执行。")
                    print("建议在生产环境中尝试执行此交易。")

                raise

    except Exception as e:
        print(f"\n创建流动性池子时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 从.env文件获取私钥
    private_key = os.getenv('PRIVATE_KEY')
    if not private_key:
        raise ValueError("未在.env文件中找到PRIVATE_KEY")

    # 示例1：获取AIOT/USDT 0.05%费率池子的价格
    fee_percent = 0.05
    pool_address, price, is_initialized, token0_name, token1_name, sqrt_price_x96, tick = get_v3_pool_price("AIOT", "USDT", fee_percent)
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

    # 示例3：创建流动性池子（模拟调用）
    print("\n创建流动性池子:")
    print(f"使用AIOT余额: {balances['AIOT']['balance']:.8f}")
    print(f"使用USDT余额: {balances['USDT']['balance']:.8f}")

    # 使用钱包余额的一半
    balance_aiot = balances["AIOT"]["balance"] * 0.9999
    balance_usdt = balances["USDT"]["balance"] * 0.9999

    print(f"使用AIOT余额的一半: {balance_aiot:.8f}")
    print(f"使用USDT余额的一半: {balance_usdt:.8f}")

    result = mint_v3_position(
        token0_name="AIOT",
        token1_name="USDT",
        fee_percent=0.05,
        amount0_desired=balance_aiot,  # 使用AIOT余额的一半
        amount1_desired=balance_usdt,  # 使用USDT余额的一半
        recipient=wallet_address,
        price_range_percent=10,  # 10%
        slippage_percent=1.0,   # 增加到1%
        deadline_minutes=20,
        send_transaction=True,
        private_key=private_key  # 传入从.env获取的私钥
    )

    if result:
        print("\n交易详情:")
        print(f"池子地址: {result['pool_address']}")
        print(f"当前价格: {result['current_price']:.8f} USDT")
        print(f"价格范围: {result['price_range']['lower']} - {result['price_range']['upper']} USDT")
        print(f"Tick范围: {result['tick_range']['lower']} - {result['tick_range']['upper']}")
        print(f"AIOT数量: {result['amounts']['token0']['desired']:.2f} (最小: {result['amounts']['token0']['min']:.2f})")
        print(f"USDT数量: {result['amounts']['token1']['desired']:.2f} (最小: {result['amounts']['token1']['min']:.2f})")
