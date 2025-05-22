from web3 import Web3
import json
import requests
from decimal import Decimal

# BSC RPC节点
BSC_RPC = "https://bsc-dataseed.binance.org/"

# 钱包地址
WALLET_ADDRESS = "0x33723ef67C37F76B990b583812891c93C2Dbe87C"

# 常见代币的合约地址
TOKENS = {
    "BNB": "0x0000000000000000000000000000000000000000",  # BNB的合约地址是0x0
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "AIOT": "0x55ad16Bd573B3365f43A9dAeB0Cc66A73821b4a5",  # 转换为小写以通过校验
}

def get_token_balance(token_address, wallet_address):
    # 创建Web3实例
    w3 = Web3(Web3.HTTPProvider(BSC_RPC))

    # 检查连接
    if not w3.is_connected():
        print("无法连接到BSC网络")
        return None

    # 如果是BNB，直接获取余额
    if token_address == "0x0000000000000000000000000000000000000000":
        balance = w3.eth.get_balance(wallet_address)
        return w3.from_wei(balance, 'ether')

    # 代币ABI - 只包含balanceOf函数
    token_abi = json.loads('[{"constant":true,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]')

    # 创建代币合约实例
    token_contract = w3.eth.contract(address=token_address, abi=token_abi)

    try:
        # 获取代币余额
        balance = token_contract.functions.balanceOf(wallet_address).call()

        # 获取代币精度
        decimals_abi = json.loads('[{"constant":true,"inputs":[],"name":"decimals","outputs":[{"name":"","type":"uint8"}],"type":"function"}]')
        decimals_contract = w3.eth.contract(address=token_address, abi=decimals_abi)
        decimals = decimals_contract.functions.decimals().call()

        # 转换余额为可读格式
        return Decimal(balance) / Decimal(10 ** decimals)
    except Exception as e:
        print(f"获取代币余额时出错: {e}")
        return None

def main():
    print(f"正在查询钱包地址 {WALLET_ADDRESS} 的BSC代币余额...\n")

    for token_name, token_address in TOKENS.items():
        balance = get_token_balance(token_address, WALLET_ADDRESS)
        if balance is not None:
            print(f"{token_name}: {balance:,.8f}")

if __name__ == "__main__":
    main()
