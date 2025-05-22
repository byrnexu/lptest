from web3 import Web3
import json
import time
from typing import Dict, Set
from datetime import datetime
import sys
from web3.middleware import geth_poa_middleware

# 连接到BSC节点
w3 = Web3(Web3.HTTPProvider('https://bsc-dataseed1.binance.org/'))

# 添加POA中间件
w3.middleware_onion.inject(geth_poa_middleware, layer=0)

# 检查连接
if not w3.is_connected():
    print("无法连接到BSC节点，请检查网络连接")
    sys.exit(1)

# 完整的ERC20 ABI
ERC20_ABI = json.loads('''[
    {
        "constant": true,
        "inputs": [],
        "name": "name",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "symbol",
        "outputs": [{"name": "", "type": "string"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "anonymous": false,
        "inputs": [
            {"indexed": true, "name": "from", "type": "address"},
            {"indexed": true, "name": "to", "type": "address"},
            {"indexed": false, "name": "value", "type": "uint256"}
        ],
        "name": "Transfer",
        "type": "event"
    }
]''')

# 已知的主要代币地址
KNOWN_TOKENS = {
}

# 存储发现的代币
discovered_tokens: Dict[str, Dict] = {}

def load_existing_data():
    """
    加载已存在的数据
    """
    global discovered_tokens
    try:
        with open('bsc_tokens.json', 'r', encoding='utf-8') as f:
            discovered_tokens = json.load(f)
    except FileNotFoundError:
        discovered_tokens = {}

def get_token_info(token_address: str) -> Dict:
    """
    获取代币信息
    """
    try:
        # 创建代币合约实例
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )

        # 获取代币信息
        try:
            name = token_contract.functions.name().call()
        except:
            name = "Unknown"

        try:
            symbol = token_contract.functions.symbol().call()
        except:
            symbol = "Unknown"

        try:
            decimals = token_contract.functions.decimals().call()
        except:
            decimals = 18

        try:
            total_supply = token_contract.functions.totalSupply().call()
        except:
            total_supply = 0

        return {
            "name": name,
            "symbol": symbol,
            "decimals": decimals,
            "total_supply": str(total_supply),
            "address": token_address,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": 1,  # 初始化为1，因为发现时就是第一次出现
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "rank": 0  # 初始排名为0
        }
    except Exception as e:
        print(f"获取代币信息失败 {token_address}: {str(e)}")
        return None

def process_transaction(tx_hash: str):
    """
    处理交易
    """
    try:
        # 获取交易收据
        tx_receipt = w3.eth.get_transaction_receipt(tx_hash)

        # 检查交易状态
        if tx_receipt['status'] != 1:
            return

        # 处理交易日志
        for log in tx_receipt['logs']:
            # 检查是否是Transfer事件
            if len(log['topics']) > 0 and log['topics'][0].hex() == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                token_address = log['address']

                # 如果是新发现的代币
                if token_address not in discovered_tokens and token_address not in KNOWN_TOKENS:
                    token_info = get_token_info(token_address)
                    if token_info:
                        discovered_tokens[token_address] = token_info
                        print(f"\n发现新代币:")
                        print(f"名称: {token_info['name']}")
                        print(f"符号: {token_info['symbol']}")
                        print(f"地址: {token_address}")
                        print(f"小数位: {token_info['decimals']}")
                        print(f"总供应量: {token_info['total_supply']}")
                        print(f"首次发现时间: {token_info['first_seen']}")
                        print(f"出现次数: 1")
                        print("-" * 50)

                        # 保存到文件
                        save_data_to_file()
                else:
                    # 更新已知代币的出现次数
                    if token_address in discovered_tokens:
                        discovered_tokens[token_address]['count'] += 1
                        discovered_tokens[token_address]['last_seen'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 每100次出现保存一次文件
                        if discovered_tokens[token_address]['count'] % 100 == 0:
                            save_data_to_file()

    except Exception as e:
        print(f"处理交易失败 {tx_hash}: {str(e)}")

def save_data_to_file():
    """
    保存数据到文件，按出现次数排序
    """
    try:
        # 将字典转换为列表并排序
        sorted_tokens = sorted(
            discovered_tokens.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )

        # 更新排名并转换回有序字典
        sorted_dict = {}
        for rank, (address, token_info) in enumerate(sorted_tokens, 1):
            token_info['rank'] = rank
            sorted_dict[address] = token_info

        # 保存到文件
        with open('bsc_tokens.json', 'w', encoding='utf-8') as f:
            json.dump(sorted_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存文件失败: {str(e)}")

def get_block_transactions(block_number: int) -> list:
    """
    获取区块中的交易
    """
    try:
        # 获取区块信息
        block = w3.eth.get_block(block_number)
        if not block:
            return []

        # 获取区块中的交易哈希
        tx_hashes = block['transactions']

        # 处理每个交易
        for tx_hash in tx_hashes:
            try:
                process_transaction(tx_hash)
            except Exception as e:
                print(f"处理交易 {tx_hash.hex()} 失败: {str(e)}")
                continue

    except Exception as e:
        print(f"获取区块 {block_number} 失败: {str(e)}")
        return []

def main():
    print("开始监控BSC链上的代币交易...")
    print("按Ctrl+C停止监控")
    print("-" * 50)

    # 加载已存在的数据
    load_existing_data()
    print(f"已加载 {len(discovered_tokens)} 个代币信息")

    # 获取最新区块
    try:
        latest_block = w3.eth.block_number
        print(f"当前区块高度: {latest_block}")
    except Exception as e:
        print(f"获取最新区块失败: {str(e)}")
        return

    try:
        while True:
            try:
                # 获取最新区块
                current_block = w3.eth.block_number

                if current_block > latest_block:
                    print(f"\n处理区块 {latest_block + 1} 到 {current_block}")

                    # 处理每个新区块
                    for block_number in range(latest_block + 1, current_block + 1):
                        get_block_transactions(block_number)

                    latest_block = current_block

                    # 每处理10个区块保存一次数据
                    if (current_block - latest_block) % 10 == 0:
                        save_data_to_file()

                # 等待新区块
                time.sleep(1)

            except Exception as e:
                print(f"处理区块时出错: {str(e)}")
                time.sleep(5)  # 出错后等待一段时间再继续
                continue

    except KeyboardInterrupt:
        print("\n停止监控")
        print(f"总共发现 {len(discovered_tokens)} 个代币")
        save_data_to_file()

if __name__ == "__main__":
    main()
